"""
GenAI Pipeline Documentation Generator
Automatically generates and maintains pipeline documentation
using LLM analysis of code and metadata.

AX Capability Demonstration:
- Auto-generates data lineage documentation
- Creates schema change summaries
- Maintains up-to-date pipeline READMEs
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import structlog
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

logger = structlog.get_logger()


@dataclass
class PipelineDocumentation:
    """Generated documentation for a data pipeline."""

    pipeline_name: str
    summary: str
    data_lineage: str
    schema_description: str
    sla_info: str
    troubleshooting_guide: str
    generated_from: str  # Source file path


class PipelineDocGenerator:
    """AI-powered pipeline documentation generator.

    Reads pipeline source code and generates comprehensive documentation
    including:
    - Pipeline purpose and overview
    - Data lineage (source → transformations → destination)
    - Schema descriptions
    - SLA and monitoring information
    - Troubleshooting guides

    This tool was built using GitHub Copilot for code generation
    and Claude for design review and prompt engineering.
    """

    def __init__(self) -> None:
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_GENAI_API_KEY"),
            temperature=0.2,
        )

    async def generate_from_file(self, file_path: str) -> PipelineDocumentation:
        """Generate documentation by analyzing a pipeline source file."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Pipeline file not found: {file_path}")

        source_code = path.read_text()
        file_name = path.stem

        # Extract structure info using AST
        structure = self._analyze_code_structure(source_code)

        prompt = ChatPromptTemplate.from_messages([
            SystemMessage(content="""You are a technical documentation expert for data engineering pipelines.
Generate comprehensive pipeline documentation in Markdown format.

Structure the documentation as:
1. **Overview**: Brief description of the pipeline's purpose
2. **Data Lineage**: Source → Processing → Destination diagram in mermaid format
3. **Schema**: Input/output schemas with field descriptions
4. **Configuration**: Environment variables and settings
5. **SLA & Monitoring**: Expected latency, alerting thresholds
6. **Troubleshooting**: Common issues and solutions

Write documentation that a new team member can understand.
Use Korean for business context descriptions, English for technical terms."""),
            HumanMessage(content=f"""Generate documentation for this data pipeline:

File: {file_path}
Classes/Functions found: {structure}

Source code:
```python
{source_code}
```

Generate comprehensive pipeline documentation in Markdown."""),
        ])

        response = await self.llm.ainvoke(prompt.format_messages())
        doc_content = response.content

        # Parse sections from the response
        sections = self._parse_doc_sections(doc_content)

        return PipelineDocumentation(
            pipeline_name=file_name,
            summary=sections.get("overview", ""),
            data_lineage=sections.get("data_lineage", ""),
            schema_description=sections.get("schema", ""),
            sla_info=sections.get("sla", ""),
            troubleshooting_guide=sections.get("troubleshooting", ""),
            generated_from=file_path,
        )

    async def generate_all_docs(self, pipeline_dir: str = "src/pipelines") -> list[PipelineDocumentation]:
        """Generate documentation for all pipeline files."""
        docs = []
        pipeline_path = Path(pipeline_dir)

        for py_file in pipeline_path.glob("*.py"):
            if py_file.name.startswith("_"):
                continue

            try:
                doc = await self.generate_from_file(str(py_file))
                docs.append(doc)

                # Save documentation
                doc_path = Path("docs") / "pipelines" / f"{py_file.stem}.md"
                doc_path.parent.mkdir(parents=True, exist_ok=True)
                doc_path.write_text(self._format_as_markdown(doc))

                logger.info("Documentation generated", pipeline=py_file.stem)
            except Exception as e:
                logger.error("Failed to generate docs", file=str(py_file), error=str(e))

        return docs

    def _analyze_code_structure(self, source_code: str) -> dict[str, Any]:
        """Analyze Python code structure using AST."""
        try:
            tree = ast.parse(source_code)
            classes = []
            functions = []
            imports = []

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    methods = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                    classes.append({"name": node.name, "methods": methods})
                elif isinstance(node, ast.FunctionDef) and not isinstance(
                    getattr(node, "_parent", None), ast.ClassDef
                ):
                    functions.append(node.name)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    if isinstance(node, ast.ImportFrom) and node.module:
                        imports.append(node.module)

            return {
                "classes": classes,
                "functions": functions,
                "key_imports": imports[:10],
            }
        except SyntaxError:
            return {"error": "Could not parse source code"}

    def _parse_doc_sections(self, content: str) -> dict[str, str]:
        """Parse documentation sections from LLM output."""
        sections = {}
        current_section = None
        current_content = []

        for line in content.split("\n"):
            if line.startswith("## ") or line.startswith("# "):
                if current_section:
                    sections[current_section] = "\n".join(current_content)
                section_name = line.lstrip("#").strip().lower()
                for key in ["overview", "lineage", "schema", "sla", "troubleshooting"]:
                    if key in section_name:
                        current_section = key
                        break
                else:
                    current_section = section_name.replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        if current_section:
            sections[current_section] = "\n".join(current_content)

        return sections

    @staticmethod
    def _format_as_markdown(doc: PipelineDocumentation) -> str:
        """Format documentation as a Markdown document."""
        return f"""# Pipeline: {doc.pipeline_name}

> Auto-generated documentation by GenAI Pipeline Doc Generator
> Source: `{doc.generated_from}`

## Overview
{doc.summary}

## Data Lineage
{doc.data_lineage}

## Schema
{doc.schema_description}

## SLA & Monitoring
{doc.sla_info}

## Troubleshooting
{doc.troubleshooting_guide}
"""
