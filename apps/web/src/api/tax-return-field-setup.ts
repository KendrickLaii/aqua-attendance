import type {
  ApiTemplateListResponse,
  ApiTemplateRequest,
} from '@/types/tax-return-field-setup'

export async function getAllTaxReturnFieldSetups(page: number, size: number) {
  const res = await $authApi('/tax_additional_info_template/get/all', {
    method: 'GET',
    params: { page, size },
    onResponseError({ response }) {
      console.error('Get all templates error:', response._data?.errors)
    },
  })
  return res as ApiTemplateListResponse
}

export async function getTaxReturnFieldSetupsByYear(year: string) {
  const res = await $authApi(`/tax_additional_info_template/get/by_year/${encodeURIComponent(year)}`, {
    method: 'GET',
    onResponseError({ response }) {
      console.error('Get template by year error:', response._data?.errors)
    },
  })
  return res as ApiTemplateListResponse
}

export async function createTaxReturnFieldSetup(
  payload: ApiTemplateRequest
) {
  const res = await $authApi('/tax_additional_info_template/create', {
    method: 'POST',
    body: payload,
    onResponseError({ response }) {
      console.error('Create template error:', response._data?.errors)
    },
  })
  return res
}

export async function updateTaxReturnFieldSetup(
  payload: ApiTemplateRequest
) {
  const res = await $authApi('/tax_additional_info_template/edit', {
    method: 'PUT',
    body: payload,
    onResponseError({ response }) {
      console.error('Update template error:', response._data?.errors)
    },
  })
  return res
}

export async function deleteTaxReturnFieldSetup(uuid: string) {
  const res = await $authApi('/tax_additional_info_template/del', {
    method: 'DELETE',
    body: { uuid, data: [uuid] },
    onResponseError({ response }) {
      console.error('Delete template error:', response._data?.errors)
    },
  })
  return res
}
