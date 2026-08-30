#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <iomanip>
#include <limits>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

const std::vector<std::pair<std::string, ggml_tensor *>> &
llama_internal_get_tensor_map(const llama_model * model);

namespace {

void quiet_log(ggml_log_level, const char *, void *) {}

struct ModelGuard {
    llama_model * ptr = nullptr;
    ~ModelGuard() { if (ptr) llama_model_free(ptr); }
};

struct BackendGuard {
    BackendGuard() { llama_backend_init(); }
    ~BackendGuard() { llama_backend_free(); }
};

std::string json_escape(const std::string & input) {
    std::string result;
    for (unsigned char ch : input) {
        switch (ch) {
            case '"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            default:
                if (ch < 0x20) {
                    const char hex[] = "0123456789abcdef";
                    result += "\\u00";
                    result += hex[(ch >> 4) & 0x0f];
                    result += hex[ch & 0x0f];
                } else {
                    result += static_cast<char>(ch);
                }
        }
    }
    return result;
}

std::vector<llama_token> tokenize(const llama_vocab * vocab, const std::string & text) {
    int32_t size = llama_tokenize(
        vocab, text.data(), static_cast<int32_t>(text.size()), nullptr, 0, false, false);
    if (size >= 0) {
        throw std::runtime_error("tokenizer size probe unexpectedly succeeded");
    }
    std::vector<llama_token> tokens(static_cast<size_t>(-size));
    const int32_t written = llama_tokenize(
        vocab, text.data(), static_cast<int32_t>(text.size()), tokens.data(),
        static_cast<int32_t>(tokens.size()), false, false);
    if (written < 0) {
        throw std::runtime_error("tokenization failed");
    }
    tokens.resize(static_cast<size_t>(written));
    return tokens;
}

ggml_tensor * find_tensor(const llama_model * model, const std::string & name) {
    for (const auto & item : llama_internal_get_tensor_map(model)) {
        if (item.first == name) return item.second;
    }
    return nullptr;
}

std::vector<float> lexical_embedding(
    const llama_model * model,
    const std::vector<llama_token> & tokens,
    int32_t dimension) {
    if (tokens.empty()) throw std::runtime_error("lexeme has no tokens");
    ggml_tensor * tensor = find_tensor(model, "token_embd.weight");
    if (!tensor || tensor->ne[0] != dimension || !ggml_is_contiguous(tensor)) {
        throw std::runtime_error("unsupported token embedding tensor");
    }
    const ggml_type_traits * traits = ggml_get_type_traits(tensor->type);
    if (!traits || !traits->to_float) {
        throw std::runtime_error("token embedding tensor cannot be dequantized");
    }
    const size_t row_bytes = ggml_row_size(tensor->type, dimension);
    std::vector<uint8_t> raw(row_bytes);
    std::vector<float> row(static_cast<size_t>(dimension));
    std::vector<float> result(static_cast<size_t>(dimension), 0.0f);
    for (llama_token token : tokens) {
        ggml_backend_tensor_get(
            tensor, raw.data(), static_cast<size_t>(token) * row_bytes, row_bytes);
        traits->to_float(raw.data(), row.data(), dimension);
        for (int32_t index = 0; index < dimension; ++index) {
            result[static_cast<size_t>(index)] += row[static_cast<size_t>(index)];
        }
    }
    for (float & value : result) value /= static_cast<float>(tokens.size());
    return result;
}

std::string piece(const llama_vocab * vocab, llama_token token) {
    std::vector<char> buffer(128);
    int32_t written = llama_token_to_piece(
        vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    if (written < 0) {
        buffer.resize(static_cast<size_t>(-written));
        written = llama_token_to_piece(
            vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    }
    if (written < 0) {
        throw std::runtime_error("token rendering failed");
    }
    return std::string(buffer.data(), static_cast<size_t>(written));
}

std::vector<float> parse_vector(const std::string & encoded, int32_t dimension) {
    std::vector<float> result;
    result.reserve(static_cast<size_t>(dimension));
    std::stringstream stream(encoded);
    std::string item;
    while (std::getline(stream, item, ',')) {
        result.push_back(std::stof(item));
    }
    if (result.size() != static_cast<size_t>(dimension)) {
        throw std::runtime_error("vector dimension mismatch");
    }
    return result;
}

struct Neighbor {
    float score;
    llama_token token;
};

std::vector<std::vector<Neighbor>> nearest_tokens(
    const llama_model * model,
    const llama_vocab * vocab,
    const std::vector<std::vector<float>> & queries,
    int32_t dimension,
    int32_t top_k,
    std::string & tensor_name) {
    ggml_tensor * tensor = find_tensor(model, "output.weight");
    tensor_name = "output.weight";
    if (!tensor) {
        tensor = find_tensor(model, "token_embd.weight");
        tensor_name = "token_embd.weight";
    }
    const int32_t vocabulary_size = llama_vocab_n_tokens(vocab);
    if (!tensor || tensor->ne[0] != dimension || tensor->ne[1] < vocabulary_size
        || !ggml_is_contiguous(tensor)) {
        throw std::runtime_error("unsupported vocabulary projection tensor");
    }
    const ggml_type_traits * traits = ggml_get_type_traits(tensor->type);
    if (!traits || !traits->to_float) {
        throw std::runtime_error("vocabulary projection cannot be dequantized");
    }

    std::vector<float> query_norms;
    for (const auto & query : queries) {
        float squared = 0.0f;
        for (float value : query) squared += value * value;
        query_norms.push_back(std::sqrt(squared));
    }
    std::vector<std::vector<Neighbor>> best(queries.size());
    const size_t row_bytes = ggml_row_size(tensor->type, dimension);
    std::vector<uint8_t> raw(row_bytes);
    std::vector<float> row(static_cast<size_t>(dimension));
    for (int32_t token_id = 0; token_id < vocabulary_size; ++token_id) {
        const auto token = static_cast<llama_token>(token_id);
        const auto attributes = llama_vocab_get_attr(vocab, token);
        if ((attributes & LLAMA_TOKEN_ATTR_CONTROL)
            || (attributes & LLAMA_TOKEN_ATTR_UNUSED)
            || (attributes & LLAMA_TOKEN_ATTR_UNKNOWN)) {
            continue;
        }
        ggml_backend_tensor_get(
            tensor, raw.data(), static_cast<size_t>(token_id) * row_bytes, row_bytes);
        traits->to_float(raw.data(), row.data(), dimension);
        float row_squared = 0.0f;
        for (float value : row) row_squared += value * value;
        const float row_norm = std::sqrt(row_squared);
        if (row_norm <= std::numeric_limits<float>::epsilon()) continue;

        for (size_t query_index = 0; query_index < queries.size(); ++query_index) {
            if (query_norms[query_index] <= std::numeric_limits<float>::epsilon()) continue;
            float dot = 0.0f;
            for (int32_t index = 0; index < dimension; ++index) {
                dot += queries[query_index][static_cast<size_t>(index)]
                    * row[static_cast<size_t>(index)];
            }
            const float score = dot / (query_norms[query_index] * row_norm);
            auto & candidates = best[query_index];
            candidates.push_back(Neighbor{score, token});
            std::sort(candidates.begin(), candidates.end(), [](const Neighbor & left, const Neighbor & right) {
                if (left.score != right.score) return left.score > right.score;
                return left.token < right.token;
            });
            if (candidates.size() > static_cast<size_t>(top_k)) candidates.pop_back();
        }
    }
    return best;
}

} // namespace

int main(int argc, char ** argv) {
    if (argc < 4) {
        std::cerr << "usage: lexeme_codec MODEL.gguf tokenize TEXT... | detokenize TOKEN_ID... | nearest TOP_K VECTOR...\n";
        return 2;
    }
    const std::string model_path = argv[1];
    const std::string mode = argv[2];
    const char * backend_env = std::getenv("OLLAMA_LIB_DIR");
    const std::string backend_dir = backend_env ? backend_env : "/usr/local/lib/ollama";

    try {
        llama_log_set(quiet_log, nullptr);
        BackendGuard backend;
        ggml_backend_load_all_from_path(backend_dir.c_str());
        llama_model_params parameters = llama_model_default_params();
        parameters.n_gpu_layers = 0;
        ModelGuard model{llama_model_load_from_file(model_path.c_str(), parameters)};
        if (!model.ptr) {
            throw std::runtime_error("model load failed");
        }
        const llama_vocab * vocab = llama_model_get_vocab(model.ptr);

        if (mode == "tokenize") {
            const int32_t dimension = llama_model_n_embd_inp(model.ptr);
            std::cout << std::setprecision(9);
            std::cout << "{\"dimension\":" << dimension
                      << ",\"items\":[";
            for (int index = 3; index < argc; ++index) {
                if (index > 3) std::cout << ',';
                const std::string text = argv[index];
                const auto tokens = tokenize(vocab, text);
                std::cout << "{\"text\":\"" << json_escape(text) << "\",\"token_ids\":[";
                for (size_t token_index = 0; token_index < tokens.size(); ++token_index) {
                    if (token_index) std::cout << ',';
                    std::cout << tokens[token_index];
                }
                const auto embedding = lexical_embedding(model.ptr, tokens, dimension);
                std::cout << "],\"embedding\":[";
                for (size_t embedding_index = 0; embedding_index < embedding.size(); ++embedding_index) {
                    if (embedding_index) std::cout << ',';
                    std::cout << embedding[embedding_index];
                }
                std::cout << "]}";
            }
            std::cout << "]}\n";
            return 0;
        }
        if (mode == "detokenize") {
            std::string text;
            for (int index = 3; index < argc; ++index) {
                text += piece(vocab, static_cast<llama_token>(std::stoi(argv[index])));
            }
            std::cout << "{\"text\":\"" << json_escape(text) << "\"}\n";
            return 0;
        }
        if (mode == "nearest") {
            if (argc < 5) throw std::runtime_error("nearest requires TOP_K and vectors");
            const int32_t dimension = llama_model_n_embd_inp(model.ptr);
            const int32_t top_k = std::stoi(argv[3]);
            if (top_k < 1 || top_k > 32) throw std::runtime_error("TOP_K must be 1..32");
            std::vector<std::vector<float>> queries;
            for (int index = 4; index < argc; ++index) {
                queries.push_back(parse_vector(argv[index], dimension));
            }
            std::string tensor_name;
            const auto results = nearest_tokens(
                model.ptr, vocab, queries, dimension, top_k, tensor_name);
            std::cout << std::setprecision(9);
            std::cout << "{\"dimension\":" << dimension
                      << ",\"tensor\":\"" << json_escape(tensor_name)
                      << "\",\"items\":[";
            for (size_t query_index = 0; query_index < results.size(); ++query_index) {
                if (query_index) std::cout << ',';
                std::cout << "{\"candidates\":[";
                for (size_t rank = 0; rank < results[query_index].size(); ++rank) {
                    if (rank) std::cout << ',';
                    const auto & candidate = results[query_index][rank];
                    std::cout << "{\"token_id\":" << candidate.token
                              << ",\"piece\":\""
                              << json_escape(piece(vocab, candidate.token))
                              << "\",\"score\":" << candidate.score << '}';
                }
                std::cout << "]}";
            }
            std::cout << "]}\n";
            return 0;
        }
        throw std::runtime_error("unknown mode: " + mode);
    } catch (const std::exception & error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
