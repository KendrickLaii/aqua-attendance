import type {
  TaxAttachmentCreatePayload,
  TaxAttachmentCreateResponse,
  TaxAttachmentEditPayload,
  TaxAttachmentEditResponse,
  TaxAttachmentGetOneResponse,
} from '@/types/attachment'

export async function createTaxAttachment(payload: TaxAttachmentCreatePayload) {
  const res = await $authApi('/tax_attachment/create', {
    method: 'POST',
    body: payload,
  })
  return res as TaxAttachmentCreateResponse
}

export async function editTaxAttachment(payload: TaxAttachmentEditPayload) {
  const res = await $authApi('/tax_attachment/edit', {
    method: 'PUT',
    body: payload,
  })
  return res as TaxAttachmentEditResponse
}

export async function getAttachmentByUuid(uuid: string) {
  const res = await $authApi(`/tax_attachment/get/${uuid}`, {
    method: 'GET',
  })
  return res as TaxAttachmentGetOneResponse
}

export async function getAttachmentByWorkingUuid(workingSectionUuid: string) {
  const res = await $authApi(`/tax_attachment/get/by_working_section_uuid/${workingSectionUuid}`, {
    method: 'GET',
  })
  return res as TaxAttachmentGetOneResponse
}

export async function deleteTaxAttachment(uuid: string) {
  const res = await $authApi('/tax_attachment/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [`${uuid}`],
    },
  })
  return res
}

export async function oneDriveGet(payload: { company_name: string, year: string, folder_name: string }) {
  const query = [
    `company_name=${encodeURIComponent(payload.company_name)}`,
    `year=${encodeURIComponent(payload.year)}`,
    `folder_name=${encodeURIComponent(payload.folder_name)}`,
  ].join('&')

  const res = await $authApi(`/user/oneDrive/get?${query}`, {
    method: 'GET',
  })
  return res
}
