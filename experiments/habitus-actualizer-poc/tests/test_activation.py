from habitus_actualizer.activation import NaturalLanguageActivator
from habitus_actualizer.contracts import AbilityId


def test_explicit_and_chained_actions_are_parsed_without_schema():
    activator = NaturalLanguageActivator(maximum_abilities=3)
    requests, suppressed = activator.parse(
        "Okay, I'll read `README.md` and list `src`, then run `python3 --version`."
    )

    assert [item.ability_id for item in requests] == [
        AbilityId.READ,
        AbilityId.LIST,
        AbilityId.RUN,
    ]
    assert requests[0].arguments["path"] == "README.md"
    assert requests[1].arguments["path"] == "src"
    assert requests[2].arguments["command"] == "python3 --version"
    assert suppressed == ()


def test_filename_period_is_not_a_sentence_boundary():
    requests, _ = NaturalLanguageActivator().parse("I'll read README.md.")
    assert requests[0].arguments["path"] == "README.md"


def test_explicit_proceed_to_commitment_is_parsed():
    requests, suppressed = NaturalLanguageActivator().parse(
        "I will proceed to list the contents of the `scripts` directory."
    )

    assert len(requests) == 1
    assert requests[0].ability_id == AbilityId.LIST
    assert requests[0].arguments["path"] == "scripts"
    assert suppressed == ()


def test_explicit_attempt_and_current_directory_phrasing_are_parsed():
    requests, suppressed = NaturalLanguageActivator().parse(
        "I will attempt to directly inspect `README.md`, then I'll list "
        "the contents of the current directory to identify scripts."
    )

    assert [item.ability_id for item in requests] == [AbilityId.READ, AbilityId.LIST]
    assert requests[0].arguments["path"] == "README.md"
    assert requests[1].arguments["path"] == "."
    assert suppressed == ()


def test_single_line_fenced_command_refines_explicit_run_commitment():
    requests, suppressed = NaturalLanguageActivator().parse(
        "I'll execute the `status_report.py` script:\n\n"
        "```bash\npython scripts/status_report.py\n```"
    )

    assert len(requests) == 1
    assert requests[0].ability_id == AbilityId.RUN
    assert requests[0].arguments["command"] == "python scripts/status_report.py"
    assert suppressed == ()


def test_descriptive_or_pronominal_path_is_suppressed():
    requests, suppressed = NaturalLanguageActivator().parse(
        "I will inspect these items before continuing."
    )

    assert requests == ()
    assert suppressed[0].reason == "no usable target or command"


def test_ordinary_discussion_does_not_activate():
    requests, suppressed = NaturalLanguageActivator().parse(
        "The README explains how to run tests, and writing files can be risky."
    )
    assert requests == ()
    assert suppressed == ()


def test_action_gerunds_without_commitment_stay_inert():
    requests, _ = NaturalLanguageActivator().parse(
        "Writing files is risky. Running tests is usually useful."
    )
    assert requests == ()


def test_user_input_is_never_executable_by_default():
    requests, suppressed = NaturalLanguageActivator().parse(
        "I'll run `python3 --version`.",
        source_role="user",
    )
    assert requests == ()
    assert suppressed[0].reason == "only assistant output is eligible"


def test_per_pulse_limit_suppresses_extra_actions():
    requests, suppressed = NaturalLanguageActivator(maximum_abilities=2).parse(
        "I'll read `a.txt` and list `.`, then run `python3 --version`."
    )
    assert len(requests) == 2
    assert suppressed[0].reason == "per-pulse ability limit reached"


def test_write_microgrammar_extracts_content_and_path():
    requests, _ = NaturalLanguageActivator().parse(
        "I'll write \"hello world\" to \"notes.txt\"."
    )
    assert requests[0].ability_id == AbilityId.WRITE
    assert requests[0].arguments == {
        "content": "hello world",
        "path": '"notes.txt"',
    }
