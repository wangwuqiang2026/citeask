import {
  File,
  FileArchive,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  Globe,
  Presentation,
} from "lucide-react";

import { fileKind, type FileKind } from "@/lib/files";
import { cn } from "@/lib/utils";

const ICONS: Record<FileKind, typeof File> = {
  pdf: FileText,
  word: FileText,
  sheet: FileSpreadsheet,
  slide: Presentation,
  image: FileImage,
  archive: FileArchive,
  url: Globe,
  text: FileText,
  code: FileCode2,
  other: File,
};

/** The row icon of a file: one glyph per kind, all from the same icon set. */
export function FileTypeIcon({
  type,
  className,
}: {
  type: string;
  className?: string;
}) {
  const Icon = ICONS[fileKind(type)];
  return (
    <Icon
      className={cn("h-4 w-4 shrink-0 text-muted", className)}
      aria-hidden="true"
    />
  );
}
