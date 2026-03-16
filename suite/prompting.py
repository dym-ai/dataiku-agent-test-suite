"""Shared prompt construction for bundled agent scripts."""


def build_agent_prompt(request):
    return "\n\n".join(
        [
            "Before starting any work, read AGENTS.md from the workspace. "
            "Use the tools and skills documented there to complete the task. "
            "Do not rely on files outside the provided workspace.",
            f"You are working in Dataiku project '{request['project_key']}'. "
            f"The project already has these source datasets: {request.get('sources', [])}.",
            request["prompt"],
            "Build and verify the required output dataset before finishing. "
            "Use the case prompt and the runtime behavior as the source of truth for task "
            "requirements. "
            "If you use Dataiku tooling that requires authentication, read the API key from the "
            "DATAIKU_API_KEY environment variable.",
        ]
    )
