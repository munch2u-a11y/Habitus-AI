import pytest
from habitus_ai import HabitusAI, OutputTrunk
from habitus_ai.audio import AudioReflexBridge, AudioReceipt

def test_audio_reflex_bridge_initialization(tmp_path):
    mind = HabitusAI(tmp_path / "test_audio_mind.sqlite")
    bridge = AudioReflexBridge(mind, piper_model="en_US-lessac-medium")
    assert bridge.mind == mind
    assert bridge.piper_model == "en_US-lessac-medium"

def test_audio_speech_synthesis_fallback(tmp_path):
    mind = HabitusAI(tmp_path / "test_audio_mind.sqlite")
    bridge = AudioReflexBridge(mind)
    
    # Test speech synthesis output (fallback synthesizer)
    receipt = bridge.speak("Hello Josh, Habitus AI voice bridge is online.", output_wav=tmp_path / "out.wav")
    assert isinstance(receipt, AudioReceipt)
    assert receipt.verified is True
    assert receipt.text == "Hello Josh, Habitus AI voice bridge is online."

def test_audio_reflex_turn_without_llm(tmp_path):
    mind = HabitusAI(tmp_path / "test_audio_mind.sqlite")
    bridge = AudioReflexBridge(mind)

    # Ingest baseline concept and record
    mind.add_concept("greeting", "Greeting", terms=["hello", "hi", "hey"], input_trunks=["HEAR"], output_trunks=["SPEAK"])
    mind.remember("Hello Josh! I am standing by to assist you.", concept_ids=["greeting"])

    # Run verbal intake -> Y-traversal -> verbal output reflex (No LLM tool call required!)
    result = bridge.process_reflex_turn("Hello Nova")
    assert result["input_text"] == "Hello Nova"
    assert result["classified_trunk"] in ("SPEAK", "LOOK", "DO", "PRIVATE")
    assert result["spoken"] is True
    assert result["receipt"].verified is True

    mind.close()
