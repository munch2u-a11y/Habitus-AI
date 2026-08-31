# Security

Habitus Actualizer deliberately separates recognition, authority, execution,
and verification.

## Safe defaults

- Only assistant-role output is eligible for activation.
- Explicit action language is required.
- At most three abilities activate from one output.
- Paths are resolved beneath one configured workspace.
- Common credential and repository-control paths are protected.
- Reads and captured process output are bounded.
- Writes are disabled until explicitly enabled.
- Every executable is denied until its basename is allowlisted.
- Commands use an argv array with `shell=False`.
- Inline Python, Node-style evaluation flags, and unapproved Python modules are
  rejected.
- Child processes receive only a small locale/path environment.
- The MCP command starts in probe-only mode; execution requires `--execute`.
- MCP callers cannot change probe/execute mode through bridge arguments.
- The bundled Streamable HTTP command binds to loopback only.

## Important limitation

Workspace containment is a path policy, not process isolation. Once a program
is allowed, the operating system—not this Python package—defines what that
program can access. Run untrusted agents and projects in a container, VM, or
restricted user account.

Do not place API keys or credentials in the agent workspace. Keep mutation and
program authority off until the integration has been exercised in dry-run mode.

The adapter has no remote authentication layer. Do not expose its HTTP endpoint
outside the local machine. A production remote deployment needs transport
authentication and process isolation supplied by the containing service.

For schema-free integration, keep `actualize_assistant_output` out of the
model-visible tool list and call it from a trusted post-generation hook. If a
general MCP host advertises it to the model, the model sees one bridge schema;
the five underlying ability schemas remain hidden, but the integration is no
longer literally schema-free.
