import type {
  NoteACFromAquaParams,
  NoteACFromAquaResponse,
  TaxComputationCreatePayload,
  TaxComputationEditPayload,
  TaxComputationListResponse,
  TaxComputationRecord,
} from '@/types/tax-computation'

export type {
  DPLGroupedData,
  GroupedDataItem,
  NoteACFromAquaParams,
  NoteACFromAquaResponse,
  TaxComputationCreatePayload,
  TaxComputationEditPayload,
  TaxComputationListResponse,
  TaxComputationRecord,
} from '@/types/tax-computation'

export async function createTaxComputation(payload: TaxComputationCreatePayload) {
  const res = await $authApi('/tax_computation/create', {
    method: 'POST',
    body: payload,
  })

  return res as {
    status_code?: number
    message?: string
    data?: string
  }
}

export async function editTaxComputation(payload: TaxComputationEditPayload) {
  const res = await $authApi('/tax_computation/edit', {
    method: 'PUT',
    body: payload,
  })

  return res as {
    status_code?: number
    message?: string
    data?: string
  }
}

export async function getTaxComputationByWorkingRecordUuid(workingRecordUuid: string) {
  const res = await $authApi(`/tax_computation/get/${workingRecordUuid}`, {
    method: 'GET',
  })

  return res as {
    status_code?: number
    message?: string
    data?: TaxComputationRecord
  }
}

export async function getAllTaxComputations(page: number, size: number) {
  const res = await $authApi('/tax_computation/get/all', {
    method: 'GET',
    params: { page, size },
  })

  return res as TaxComputationListResponse
}

export async function deleteTaxComputation(uuid: string) {
  const res = await $authApi('/tax_computation/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [`${uuid}`],
    },
  })

  return res
}

export async function getNoteACFromAqua(params: NoteACFromAquaParams) {
  const res = await $authApi('/aqua/audit/noteToAc/get', {
    method: 'GET',
    params,
  })

  return res as NoteACFromAquaResponse
}

function sanitizeFilename(name: string): string {
  // Windows reserved: \ / : * ? " < > |
  return name.replace(/[\\/:*?"<>|]/g, '-').replace(/\s+/g, ' ').trim()
}

export async function printScheduleOne(
  taxComputationUuid: string,
  workingRecordUuid: string,
  companyNameEn: string,
  yearOfAssessmentLy: string | number,
  yearOfAssessment: string | number,
): Promise<
  | { blob: Blob; filename: string; errorMessage: '' }
  | { blob: null; filename: ''; errorMessage: string }
> {
  const accessToken = useCookie('accessToken').value

  const res = await $authApi.raw('/printing/schedule', {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'Content-Type': 'application/json',
      ...(accessToken ? { 'auth-token': accessToken } : {}),
    },
    body: {
      tax_computation_uuid: taxComputationUuid,
      working_record_uuid: workingRecordUuid,
    },
    responseType: 'blob',
  })

  const blob = res._data as Blob
  const response = (res as any).response as Response | undefined

  const contentType = (response?.headers?.get('content-type') ?? '').toLowerCase()
  const blobType = String((blob as any)?.type ?? '').toLowerCase()

  // Backend may return HTTP 200 with JSON error body but incorrect/missing content-type.
  // Detect via content-type, blob.type, and a cheap JSON sniff.
  const looksLikeJsonByType = contentType.includes('json') || blobType.includes('json')
  const headText = await blob.slice(0, 64).text()
  const trimmedHead = headText.trimStart()
  const looksLikeJsonByContent = trimmedHead.startsWith('{') || trimmedHead.startsWith('[')

  if (looksLikeJsonByType || looksLikeJsonByContent) {
    const text = await blob.text()
    let message = text
    try {
      const parsed = JSON.parse(text) as { status_code?: number; message?: string }
      if (typeof parsed?.status_code === 'number' && parsed.status_code !== 200)
        message = parsed.message ?? text
      else if (parsed?.message)
        message = parsed.message
    }
    catch {
      // keep raw text
    }

    // If it *really* is JSON, don't treat as downloadable file.
    if (looksLikeJsonByType || looksLikeJsonByContent)
      return { blob: null, filename: '', errorMessage: message }
  }

  const disposition = response?.headers?.get('content-disposition') ?? ''

  const filenameFromHeader = (() => {
    // RFC5987: filename*=utf-8''...
    const star = disposition.match(/filename\*\s*=\s*([^;]+)/i)?.[1]?.trim()
    if (star) {
      const v = star.replace(/^UTF-8''/i, '').replace(/^["']|["']$/g, '')
      try { return decodeURIComponent(v) } catch { return v }
    }

    const plain = disposition.match(/filename\s*=\s*([^;]+)/i)?.[1]?.trim()
    if (plain) return plain.replace(/^["']|["']$/g, '')

    return 'ScheduleOne'
  })()

  const baseName = `${companyNameEn} - Tax computataion ${yearOfAssessmentLy}/${yearOfAssessment}`
  const filename = sanitizeFilename(baseName || filenameFromHeader || 'ScheduleOne')

  return { blob, filename, errorMessage: '' }
}
