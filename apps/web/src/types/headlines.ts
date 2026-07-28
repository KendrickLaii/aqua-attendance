export interface Content {
  id?: number
  uuid?: string
  title?: string | null
  index_type?: string | null
  remark?: string | null
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface HeadlinesProperties {
  data?: {
    content: Content[]
    count: number
  }
}
