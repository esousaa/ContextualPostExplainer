import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.application.live_explanation_service import LiveExplanationService
from app.config import Settings, get_settings
from app.observability.redaction import redact_text

MatrixName = Literal["search", "llm", "all"]

SEARCH_PROVIDER_CONFIGS: dict[str, dict[str, Any]] = {
    "search_tavily": {
        "search_provider": "tavily",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "openai_vision_model": "gpt-4o",
    },
    "search_brave": {
        "search_provider": "brave",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "openai_vision_model": "gpt-4o",
    },
    "search_composite": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "openai_vision_model": "gpt-4o",
    },
}

LLM_CONFIGS: dict[str, dict[str, Any]] = {
    "baseline_4o_small": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "openai_vision_model": "gpt-4o",
    },
    "baseline_4o_large_embedding": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-4o",
        "openai_judge_model": "gpt-4o-mini",
        "openai_embedding_model": "text-embedding-3-large",
        "openai_vision_model": "gpt-4o",
    },
    "newer_full": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-5.1",
        "openai_judge_model": "gpt-5-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "openai_vision_model": "gpt-5.1",
    },
    "newer_full_large_embedding": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-5.1",
        "openai_judge_model": "gpt-5-mini",
        "openai_embedding_model": "text-embedding-3-large",
        "openai_vision_model": "gpt-5.1",
    },
    "newer_mini": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-5-mini",
        "openai_judge_model": "gpt-5-mini",
        "openai_embedding_model": "text-embedding-3-small",
        "openai_vision_model": "gpt-5.1",
    },
    "newer_mini_large_embedding": {
        "search_provider": "composite",
        "openai_generation_model": "gpt-5-mini",
        "openai_judge_model": "gpt-5-mini",
        "openai_embedding_model": "text-embedding-3-large",
        "openai_vision_model": "gpt-5.1",
    },
}


def main() -> None:
    args = _parse_args()
    urls = _read_urls(args.url_file, args.max_urls)
    configs = _configs(args.matrix, args.config)
    configs = _override_search_provider(configs, args.search_provider)
    group_id = args.group_id or _default_group_id(args.matrix)

    if args.dry_run:
        _print_plan(urls, configs, group_id)
        return

    asyncio.run(_run_matrix(urls, configs, group_id))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run comparative live analysis for URL and configuration matrices.",
    )
    parser.add_argument(
        "--url-file",
        type=Path,
        default=Path("../_Docs_Projeto/urls_rerun_live.txt"),
        help="Text file with one Bluesky URL per line.",
    )
    parser.add_argument(
        "--matrix",
        choices=["search", "llm", "all"],
        default="search",
        help="Comparison matrix to execute.",
    )
    parser.add_argument("--group-id", help="Comparison group id stored in run artifacts.")
    parser.add_argument(
        "--config",
        action="append",
        help=(
            "Run only one config id. Can be passed multiple times. "
            "Valid values depend on --matrix, e.g. newer_full or search_composite."
        ),
    )
    parser.add_argument(
        "--search-provider",
        choices=["brave", "tavily", "composite"],
        help="Override the search provider for the selected config(s).",
    )
    parser.add_argument("--max-urls", type=int, help="Limit URLs for smoke runs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned matrix without calling external providers.",
    )
    return parser.parse_args()


def _read_urls(path: Path, max_urls: int | None) -> list[str]:
    urls = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    return urls[:max_urls] if max_urls else urls


def _configs(matrix: MatrixName, selected_configs: list[str] | None) -> dict[str, dict[str, Any]]:
    if matrix == "search":
        configs = SEARCH_PROVIDER_CONFIGS
    elif matrix == "llm":
        configs = LLM_CONFIGS
    else:
        configs = {**SEARCH_PROVIDER_CONFIGS, **LLM_CONFIGS}

    if not selected_configs:
        return configs

    unknown = sorted(set(selected_configs) - set(configs))
    if unknown:
        valid = ", ".join(sorted(configs))
        raise SystemExit(
            f"Unknown config id(s): {', '.join(unknown)}. Valid values: {valid}"
        )

    return {key: configs[key] for key in selected_configs}


def _override_search_provider(
    configs: dict[str, dict[str, Any]],
    search_provider: str | None,
) -> dict[str, dict[str, Any]]:
    if not search_provider:
        return configs
    return {
        key: {
            **value,
            "search_provider": search_provider,
        }
        for key, value in configs.items()
    }


async def _run_matrix(
    urls: list[str],
    configs: dict[str, dict[str, Any]],
    group_id: str,
) -> None:
    base_settings = get_settings()
    results = []
    for config_id, overrides in configs.items():
        settings = _settings_for_config(base_settings, group_id, config_id, overrides)
        service = LiveExplanationService(settings)
        for url in urls:
            result = await _run_one(service, config_id, url)
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)
    _write_summary(group_id, results)


async def _run_one(
    service: LiveExplanationService,
    config_id: str,
    url: str,
) -> dict[str, Any]:
    started = datetime.now(UTC).isoformat()
    try:
        response = await service.explain_url(url=url, include_debug=False)
    except Exception as exc:
        return {
            "config_id": config_id,
            "url": url,
            "started_at": started,
            "status": "failed_config",
            "error": redact_text(str(exc)),
        }

    return {
        "config_id": config_id,
        "url": url,
        "started_at": started,
        "status": "completed" if response.explanation else "no_explanation",
        "confidence": response.confidence,
        "bullet_count": len(response.explanation),
        "source_count": len(response.sources),
        "warning_count": len(response.warnings),
        "execution_time_ms": response.execution_time_ms,
    }


def _settings_for_config(
    base_settings: Settings,
    group_id: str,
    config_id: str,
    overrides: dict[str, Any],
) -> Settings:
    return base_settings.model_copy(
        update={
            **overrides,
            "comparison_group_id": group_id,
            "comparison_config_id": config_id,
        }
    )


def _write_summary(group_id: str, results: list[dict[str, Any]]) -> None:
    directory = Path("runs") / "comparisons"
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "comparison_group_id": group_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "results": results,
    }
    (directory / f"{group_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _print_plan(
    urls: list[str],
    configs: dict[str, dict[str, Any]],
    group_id: str,
) -> None:
    print(
        json.dumps(
            {
                "comparison_group_id": group_id,
                "url_count": len(urls),
                "config_count": len(configs),
                "planned_runs": len(urls) * len(configs),
                "configs": list(configs),
                "urls": urls,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _default_group_id(matrix: MatrixName) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"{matrix}_{timestamp}"


if __name__ == "__main__":
    main()
