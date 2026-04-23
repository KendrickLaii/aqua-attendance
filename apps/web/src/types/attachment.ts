/** Drop zone / Review UI item (local File or restored from API with URL). */
export interface TaxAttachmentListItem {
  name: string
  url: string
  size?: number
  file?: File
}

/** Exposed methods on `Review.vue` for attachment save/load. */
export interface TaxAttachmentReviewExpose {
  getAttachmentListForPayload: () => Promise<unknown[]>
  getAttachmentRecordUuid: () => string
}

export interface TaxAttachmentCreatePayload {
  attachment_list: unknown[]
  working_record_uuid: string
}

export interface TaxAttachmentEditPayload {
  attachment_list: unknown[]
  working_record_uuid: string
  uuid: string
}

export interface TaxAttachmentRecord {
  id?: number
  uuid?: string
  working_record_uuid?: string
  attachment_list?: unknown[]
  created_at?: string | null
  updated_at?: string | null
  deleted_at?: string | null
}

export interface TaxAttachmentCreateResponse {
  status_code?: number
  message?: string
  data?: string
}

export interface TaxAttachmentEditResponse {
  status_code?: number
  message?: string
  data?: string
}

export interface TaxAttachmentGetOneResponse {
  status_code?: number
  message?: string
  data?: TaxAttachmentRecord
}
