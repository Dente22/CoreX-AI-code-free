export type PatchHighlightType = 'add' | 'delete' | 'modify';

export interface FilePatchHighlight {
  line: number;
  type: PatchHighlightType;
  old?: string;
  new?: string;
  endLine?: number;
  displayLine?: number;
}

export interface EditorPatchEvent {
  path: string;
  content: string;
  highlights: FilePatchHighlight[];
}
