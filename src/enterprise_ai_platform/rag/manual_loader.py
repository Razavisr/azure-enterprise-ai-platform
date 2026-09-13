from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter


@dataclass(frozen=True)
class ManualChunk:
    id: str
    equipment_model: str
    document_title: str
    section_title: str
    content: str
    source: str
    chunk_order: int


def load_manual_chunks(manuals_dir: Path) -> list[ManualChunk]:
    manual_paths = sorted(manuals_dir.rglob("*.md"))
    if not manual_paths:
        raise FileNotFoundError(f"No Markdown manuals found in {manuals_dir}")

    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[
            ("#", "document_title"),
            ("##", "section_title"),
        ]
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=80,
    )

    chunks: list[ManualChunk] = []

    for path in manual_paths:
        equipment_model = path.parent.name.upper()
        source = path.relative_to(manuals_dir).as_posix()
        sections = header_splitter.split_text(path.read_text(encoding="utf-8"))

        chunk_order = 0
        for section in sections:
            document_title = str(section.metadata.get("document_title", path.stem))
            section_title = str(section.metadata.get("section_title", "Safety notice"))

            for piece in text_splitter.split_text(section.page_content):
                chunk_id = sha256(f"{source}:{chunk_order}".encode()).hexdigest()

                chunks.append(
                    ManualChunk(
                        id=chunk_id,
                        equipment_model=equipment_model,
                        document_title=document_title,
                        section_title=section_title,
                        content=f"{equipment_model} | {section_title}\n{piece.strip()}",
                        source=source,
                        chunk_order=chunk_order,
                    )
                )
                chunk_order += 1

    return chunks
