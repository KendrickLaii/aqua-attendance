import type {
  CurrencyEditPayload,
  CurrencyListResponse,
  CurrencyMutationResponse,
  CurrencyPayload,
} from '@/types/currency'

export async function getAllCurrency(page: number, size: number) {
  const res = await $authApi('/currency/get/all', {
    method: 'GET',
    params: { page, size },
  })
  return res as CurrencyListResponse
}

export async function getCurrencyByUuid(uuid: string) {
  const res = await $authApi(`/currency/get/${uuid}`, {
    method: 'GET',
  })
  return res as CurrencyMutationResponse
}
export async function createCurrency(payload: CurrencyPayload) {
  const res = await $authApi('/currency/create', {
    method: 'POST',
    body: payload,
  })
  return res as CurrencyMutationResponse
}

export async function updateCurrency(uuid: string, payload: CurrencyPayload) {
  const req: CurrencyEditPayload = { ...payload, uuid }
  const res = await $authApi('/currency/edit', {
    method: 'PUT',
    body: req,
  })
  return res as CurrencyMutationResponse
}

export async function deleteCurrency(uuid: string) {
  const res = await $authApi('/currency/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [`${uuid}`],
    },
  })
  return res as CurrencyMutationResponse
}
