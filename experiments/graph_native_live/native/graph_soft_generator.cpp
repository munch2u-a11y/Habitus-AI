#include "llama.h"
#include "ggml.h"
#include "ggml-backend.h"

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <numeric>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

// Internal but exported by the exact llama.cpp revision pinned by Ollama.
const std::vector<std::pair<std::string, ggml_tensor *>> &
llama_internal_get_tensor_map(const llama_model * model);

namespace {

void quiet_log(ggml_log_level, const char *, void *) {}

struct ContextGuard {
    llama_context * ptr = nullptr;
    ~ContextGuard() { if (ptr) llama_free(ptr); }
};

struct ModelGuard {
    llama_model * ptr = nullptr;
    ~ModelGuard() { if (ptr) llama_model_free(ptr); }
};

struct SamplerGuard {
    llama_sampler * ptr = nullptr;
    ~SamplerGuard() { if (ptr) llama_sampler_free(ptr); }
};

struct BackendGuard {
    BackendGuard() { llama_backend_init(); }
    ~BackendGuard() { llama_backend_free(); }
};

struct Activation {
    std::string basis;
    float value = 0.0f;
};

struct Packet {
    bool opaque = false;
    int32_t dimension = 0;
    int32_t rows = 0;
    std::vector<Activation> activations;
    std::vector<float> values;
};

const std::map<std::string, std::vector<std::string>> BASIS = {
    {"speak",       {" answer", " respond", " say"}},
    {"greeting",    {" hello", " welcome", " greetings"}},
    {"warm",        {" warm", " friendly", " kind"}},
    {"question",    {" answer", " explain", " helpful"}},
    {"clear",       {" clear", " direct", " concise"}},
    {"memory",      {" remember", " recall", " familiar"}},
    {"uncertain",   {" uncertain", " careful", " honest"}},
    {"gratitude",   {" thanks", " appreciate", " welcome"}},
    {"observation", {" observe", " notice", " describe"}},
    {"action",      {" act", " execute", " complete"}},
    // Preference-derived valence slots.  Their activations are computed from the
    // graph's habitual preference state (Layer 2 preference nodes and Layer 4
    // membrane weights), never from any word the user typed.
    {"affinity",    {" trust", " friend", " glad"}},
    {"caution",     {" cautious", " wary", " guarded"}},
    {"withhold",    {" decline", " withhold", " refrain"}},
};

std::string json_escape(const std::string & input) {
    std::string result;
    result.reserve(input.size() + 8);
    for (unsigned char ch : input) {
        switch (ch) {
            case '\"': result += "\\\""; break;
            case '\\': result += "\\\\"; break;
            case '\b': result += "\\b"; break;
            case '\f': result += "\\f"; break;
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

std::vector<llama_token> tokenize(
    const llama_vocab * vocab,
    const std::string & text,
    bool add_special,
    bool parse_special) {
    int32_t size = llama_tokenize(
        vocab, text.data(), static_cast<int32_t>(text.size()), nullptr, 0,
        add_special, parse_special);
    if (size >= 0) {
        throw std::runtime_error("tokenizer size probe unexpectedly succeeded");
    }
    std::vector<llama_token> tokens(static_cast<size_t>(-size));
    const int32_t written = llama_tokenize(
        vocab, text.data(), static_cast<int32_t>(text.size()), tokens.data(),
        static_cast<int32_t>(tokens.size()), add_special, parse_special);
    if (written < 0) {
        throw std::runtime_error("tokenization failed");
    }
    tokens.resize(static_cast<size_t>(written));
    return tokens;
}

ggml_tensor * find_tensor(const llama_model * model, const std::string & name) {
    for (const auto & item : llama_internal_get_tensor_map(model)) {
        if (item.first == name) {
            return item.second;
        }
    }
    return nullptr;
}

std::vector<float> exact_input_embeddings(
    const llama_model * model,
    const std::vector<llama_token> & tokens,
    int32_t n_embd) {
    ggml_tensor * tensor = find_tensor(model, "token_embd.weight");
    if (!tensor) {
        throw std::runtime_error("token_embd.weight not found");
    }
    if (tensor->ne[0] != n_embd || !ggml_is_contiguous(tensor)) {
        throw std::runtime_error("unsupported token embedding tensor layout");
    }
    const ggml_type_traits * traits = ggml_get_type_traits(tensor->type);
    if (!traits || !traits->to_float) {
        throw std::runtime_error("token embedding tensor has no to_float implementation");
    }
    const size_t row_bytes = ggml_row_size(tensor->type, n_embd);
    if (tensor->nb[1] != row_bytes) {
        throw std::runtime_error("unexpected token embedding row stride");
    }
    std::vector<uint8_t> raw(row_bytes);
    std::vector<float> result(tokens.size() * static_cast<size_t>(n_embd));
    for (size_t i = 0; i < tokens.size(); ++i) {
        const llama_token token = tokens[i];
        if (token < 0 || token >= tensor->ne[1]) {
            throw std::runtime_error("token outside embedding table");
        }
        ggml_backend_tensor_get(
            tensor, raw.data(), static_cast<size_t>(token) * row_bytes, row_bytes);
        traits->to_float(
            raw.data(), result.data() + i * static_cast<size_t>(n_embd), n_embd);
    }
    return result;
}

float row_norm(const float * row, int32_t n_embd) {
    double squared = 0.0;
    for (int32_t i = 0; i < n_embd; ++i) {
        squared += static_cast<double>(row[i]) * row[i];
    }
    return static_cast<float>(std::sqrt(squared));
}

std::vector<float> semantic_slot(
    const llama_model * model,
    const llama_vocab * vocab,
    const std::vector<std::string> & anchors,
    int32_t n_embd,
    float activation) {
    std::vector<float> slot(static_cast<size_t>(n_embd), 0.0f);
    std::vector<float> norms;
    size_t rows = 0;
    for (const std::string & anchor : anchors) {
        const auto tokens = tokenize(vocab, anchor, false, false);
        const auto embeddings = exact_input_embeddings(model, tokens, n_embd);
        for (size_t row = 0; row < tokens.size(); ++row) {
            const float * source = embeddings.data() + row * static_cast<size_t>(n_embd);
            norms.push_back(row_norm(source, n_embd));
            for (int32_t column = 0; column < n_embd; ++column) {
                slot[static_cast<size_t>(column)] += source[column];
            }
            ++rows;
        }
    }
    if (rows == 0) {
        throw std::runtime_error("semantic basis produced no token rows");
    }
    for (float & value : slot) {
        value /= static_cast<float>(rows);
    }
    const float current_norm = row_norm(slot.data(), n_embd);
    const float target_norm = std::accumulate(norms.begin(), norms.end(), 0.0f)
        / static_cast<float>(norms.size());
    if (current_norm > 0.0f) {
        // Keep every slot on the model's familiar embedding-norm shell while
        // allowing graph activation to make only a bounded amplitude change.
        const float bounded = std::max(0.0f, std::min(1.0f, activation));
        const float scale = target_norm * (0.85f + 0.30f * bounded) / current_norm;
        for (float & value : slot) {
            value *= scale;
        }
    }
    return slot;
}

Packet load_packet(const std::string & path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("cannot open graph packet: " + path);
    }
    std::string header;
    std::getline(input, header);
    Packet packet;
    if (header == "HABITUS_OPAQUE_PACKET_V1") {
        packet.opaque = true;
        if (!(input >> packet.dimension >> packet.rows)) {
            throw std::runtime_error("opaque packet is missing its shape");
        }
        if (packet.dimension < 1 || packet.dimension > 16384
                || packet.rows < 1 || packet.rows > 8) {
            throw std::runtime_error("opaque packet shape is outside safety bounds");
        }
        const size_t count = static_cast<size_t>(packet.dimension)
            * static_cast<size_t>(packet.rows);
        packet.values.resize(count);
        for (float & value : packet.values) {
            if (!(input >> value) || !std::isfinite(value)) {
                throw std::runtime_error("opaque packet has missing or invalid values");
            }
        }
        std::string trailing;
        if (input >> trailing) {
            throw std::runtime_error("opaque packet has trailing data");
        }
        return packet;
    }
    if (header != "HABITUS_SOFT_PACKET_V1") {
        throw std::runtime_error("unsupported graph packet header");
    }
    std::string line;
    while (std::getline(input, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        std::istringstream stream(line);
        Activation activation;
        std::string trailing;
        if (!(stream >> activation.basis >> activation.value) || (stream >> trailing)) {
            throw std::runtime_error("malformed activation line: " + line);
        }
        if (BASIS.find(activation.basis) == BASIS.end()) {
            throw std::runtime_error("unknown semantic basis: " + activation.basis);
        }
        if (!std::isfinite(activation.value) || activation.value <= 0.0f
                || activation.value > 1.0f) {
            throw std::runtime_error("activation must be in (0, 1]");
        }
        packet.activations.push_back(activation);
    }
    if (packet.activations.empty()) {
        throw std::runtime_error("graph packet has no activations");
    }
    if (packet.activations.size() > 8) {
        throw std::runtime_error("graph packet exceeds the eight-slot safety cap");
    }
    packet.rows = static_cast<int32_t>(packet.activations.size());
    return packet;
}

std::vector<float> place_on_embedding_shell(
    const std::vector<float> & opaque,
    int32_t rows,
    int32_t n_embd,
    const std::vector<float> & structural_rows) {
    if (opaque.size() != static_cast<size_t>(rows) * static_cast<size_t>(n_embd)
            || structural_rows.empty()
            || structural_rows.size() % static_cast<size_t>(n_embd) != 0) {
        throw std::runtime_error("cannot calibrate malformed opaque rows");
    }
    const size_t structural_count = structural_rows.size() / static_cast<size_t>(n_embd);
    float target_norm = 0.0f;
    for (size_t row = 0; row < structural_count; ++row) {
        target_norm += row_norm(
            structural_rows.data() + row * static_cast<size_t>(n_embd), n_embd);
    }
    target_norm /= static_cast<float>(structural_count);

    std::vector<float> result = opaque;
    for (int32_t row = 0; row < rows; ++row) {
        float * values = result.data() + static_cast<size_t>(row) * n_embd;
        const float current_norm = row_norm(values, n_embd);
        if (current_norm <= 0.0f) {
            throw std::runtime_error("opaque packet contains a zero row");
        }
        const float scale = target_norm / current_norm;
        for (int32_t column = 0; column < n_embd; ++column) {
            values[column] *= scale;
        }
    }
    return result;
}

void append_rows(std::vector<float> & output, const std::vector<float> & rows) {
    output.insert(output.end(), rows.begin(), rows.end());
}

std::string token_piece(const llama_vocab * vocab, llama_token token) {
    std::vector<char> buffer(128);
    int32_t written = llama_token_to_piece(
        vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    if (written < 0) {
        buffer.resize(static_cast<size_t>(-written));
        written = llama_token_to_piece(
            vocab, token, buffer.data(), static_cast<int32_t>(buffer.size()), 0, true);
    }
    if (written < 0) {
        throw std::runtime_error("failed to render generated token");
    }
    return std::string(buffer.data(), static_cast<size_t>(written));
}

} // namespace

int main(int argc, char ** argv) {
    if (argc < 3 || argc > 6) {
        std::cerr << "usage: graph_soft_generator MODEL.gguf PACKET [MAX_TOKENS] [SEED] [BACKEND_DIR]\n";
        return 2;
    }
    const std::string model_path = argv[1];
    const std::string packet_path = argv[2];
    const int32_t maximum_tokens = argc >= 4 ? std::stoi(argv[3]) : 64;
    const uint32_t seed = argc >= 5 ? static_cast<uint32_t>(std::stoul(argv[4])) : 42u;
    const char * backend_env = std::getenv("OLLAMA_LIB_DIR");
    const std::string backend_dir = argc >= 6
        ? argv[5]
        : (backend_env ? backend_env : "/usr/local/lib/ollama");

    try {
        if (!std::getenv("HABITUS_NATIVE_VERBOSE")) {
            llama_log_set(quiet_log, nullptr);
        }
        const Packet packet = load_packet(packet_path);
        BackendGuard backend;
        ggml_backend_load_all_from_path(backend_dir.c_str());
        // Ollama ships accelerator backends in subdirectories, so the CPU-only
        // top level is not enough to offload.  Load whichever ones exist.
        if (const char * gpu_backend_dir = std::getenv("HABITUS_NATIVE_GPU_BACKEND_DIR")) {
            ggml_backend_load_all_from_path(gpu_backend_dir);
        } else {
            for (const char * candidate : {"/vulkan", "/rocm_v7_2"}) {
                ggml_backend_load_all_from_path((backend_dir + candidate).c_str());
            }
        }

        llama_model_params model_params = llama_model_default_params();
        // CPU by default so results stay byte-reproducible across machines.  Set
        // HABITUS_NATIVE_GPU_LAYERS to offload onto whichever ggml backend
        // ggml_backend_load_all_from_path found (Vulkan / ROCm / CUDA).
        model_params.n_gpu_layers = 0;
        if (const char * gpu_layers_env = std::getenv("HABITUS_NATIVE_GPU_LAYERS")) {
            try {
                model_params.n_gpu_layers = std::stoi(gpu_layers_env);
            } catch (const std::exception &) {
                throw std::runtime_error("HABITUS_NATIVE_GPU_LAYERS must be an integer");
            }
        }
        ModelGuard model{llama_model_load_from_file(model_path.c_str(), model_params)};
        if (!model.ptr) {
            throw std::runtime_error("llama_model_load_from_file failed");
        }
        const llama_vocab * vocab = llama_model_get_vocab(model.ptr);
        const int32_t n_embd = llama_model_n_embd_inp(model.ptr);

        // Only fixed role delimiters are exact token rows. No user text,
        // retrieved memory text, or rendered graph context enters this batch.
        const auto prefix_tokens = tokenize(vocab, "<|im_start|>user\n", true, true);
        const bool forced_empty_think = std::getenv("HABITUS_NATIVE_SKIP_THINK") != nullptr;
        const std::string suffix = forced_empty_think
            ? "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
            : "<|im_end|>\n<|im_start|>assistant\n";
        const auto suffix_tokens = tokenize(vocab, suffix, false, true);
        const auto prefix_embeddings = exact_input_embeddings(
            model.ptr, prefix_tokens, n_embd);
        const auto suffix_embeddings = exact_input_embeddings(
            model.ptr, suffix_tokens, n_embd);
        std::vector<float> input_embeddings;
        append_rows(input_embeddings, prefix_embeddings);
        if (packet.opaque) {
            if (packet.dimension != n_embd) {
                throw std::runtime_error(
                    "opaque graph width does not match the model input width");
            }
            std::vector<float> structural = prefix_embeddings;
            append_rows(structural, suffix_embeddings);
            append_rows(input_embeddings, place_on_embedding_shell(
                packet.values, packet.rows, n_embd, structural));
        } else {
            for (const Activation & activation : packet.activations) {
                append_rows(input_embeddings, semantic_slot(
                    model.ptr, vocab, BASIS.at(activation.basis), n_embd, activation.value));
            }
        }
        append_rows(input_embeddings, suffix_embeddings);
        const int32_t input_rows = static_cast<int32_t>(
            input_embeddings.size() / static_cast<size_t>(n_embd));

        llama_context_params context_params = llama_context_default_params();
        context_params.n_ctx = static_cast<uint32_t>(std::max(128, input_rows + maximum_tokens + 8));
        context_params.n_batch = static_cast<uint32_t>(std::max(32, input_rows));
        context_params.n_ubatch = context_params.n_batch;
        context_params.no_perf = true;
        ContextGuard context{llama_init_from_model(model.ptr, context_params)};
        if (!context.ptr) {
            throw std::runtime_error("llama_init_from_model failed");
        }
        llama_set_n_threads(context.ptr, 4, 4);

        llama_batch batch{};
        batch.n_tokens = input_rows;
        batch.embd = input_embeddings.data();
        if (llama_decode(context.ptr, batch) != 0) {
            throw std::runtime_error("initial embedding decode failed");
        }

        auto sampler_params = llama_sampler_chain_default_params();
        sampler_params.no_perf = true;
        SamplerGuard sampler{llama_sampler_chain_init(sampler_params)};
        llama_sampler_chain_add(sampler.ptr, llama_sampler_init_top_k(40));
        llama_sampler_chain_add(sampler.ptr, llama_sampler_init_top_p(0.90f, 1));
        llama_sampler_chain_add(sampler.ptr, llama_sampler_init_temp(0.70f));
        llama_sampler_chain_add(sampler.ptr, llama_sampler_init_dist(seed));

        std::string response;
        int32_t generated = 0;
        for (; generated < maximum_tokens; ++generated) {
            const llama_token token = llama_sampler_sample(sampler.ptr, context.ptr, -1);
            if (llama_vocab_is_eog(vocab, token)) {
                break;
            }
            response += token_piece(vocab, token);
            llama_token mutable_token = token;
            llama_batch next = llama_batch_get_one(&mutable_token, 1);
            if (llama_decode(context.ptr, next) != 0) {
                throw std::runtime_error("generated-token decode failed");
            }
        }

        std::cout << std::setprecision(8);
        std::cout << "{\n";
        std::cout << "  \"response\": \"" << json_escape(response) << "\",\n";
        std::cout << "  \"generated_tokens\": " << generated << ",\n";
        std::cout << "  \"soft_slots\": " << packet.rows << ",\n";
        std::cout << "  \"structural_rows\": "
                  << (prefix_tokens.size() + suffix_tokens.size()) << ",\n";
        std::cout << "  \"embedding_rows\": " << input_rows << ",\n";
        std::cout << "  \"model_received_prompt_text\": false,\n";
        std::cout << "  \"model_received_user_tokens\": false,\n";
        std::cout << "  \"forced_empty_think\": "
                  << (forced_empty_think ? "true" : "false") << ",\n";
        std::cout << "  \"semantic_codebook_used\": "
                  << (packet.opaque ? "false" : "true") << ",\n";
        std::cout << "  \"adapter_kind\": \""
                  << (packet.opaque
                      ? "opaque_graph_state_native_1024_v0"
                      : "train_free_semantic_codebook_v0")
                  << "\"\n";
        std::cout << "}\n";
        return 0;
    } catch (const std::exception & error) {
        std::cerr << "error: " << error.what() << '\n';
        return 1;
    }
}
