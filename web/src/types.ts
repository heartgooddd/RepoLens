export type FolderId = 'root' | 'utils' | 'docs' | 'main' | 'flow' | 'nodes'

export interface SourceFile {
  path: string
  purpose: string
  line: number
  excerpt: string
}

export interface FolderCard {
  id: FolderId
  label: string
  title: string
  description: string
  files: SourceFile[]
  next: string
}

export interface RunParameters {
  language: 'zh' | 'en'
  topics: 3 | 5
  scenario: 'success' | 'failure'
}

export type RunState =
  | { status: 'idle' }
  | { status: 'running'; parameters: RunParameters; step: number }
  | { status: 'success'; parameters: RunParameters }
  | { status: 'error' | 'stopped'; parameters: RunParameters; step: number }
