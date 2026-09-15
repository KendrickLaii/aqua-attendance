import type { AquaAuditClientProfile, Content, FuzzySearchResponse } from '@/types/client'

export async function createClient(formData: Content) {
  return await $authApi('/client_profile/create', {
    method: 'POST',
    body: formData,
  })
}

export async function getAllClients(page: number, size: number) {
  return await $authApi('/client_profile/get/all', {
    method: 'GET',
    params: {
      page,
      size,
    },
    onResponseError({ response }) {
      console.log(response._data.errors)
    },
  })
}

export async function updateClient(formData: Partial<Content>) {
  return await $authApi('/client_profile/edit', {
    method: 'PUT',
    body: formData,
  })
}

export async function deleteClient(uuid: string) {
  return await $authApi('/client_profile/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [`${uuid}`], // update this if handle batch delete
    },
  })
}

export async function searchClientByCompanyNumberAndYearOfAssessment(companyNo: string, yearOfAssessment: string) {
  return await $authApi('/client_profile/search', {
    method: 'GET',
    params: {
      company_no: companyNo,
      year_of_assessment: yearOfAssessment,
    },
  })
}

export async function getClientByUuid(uuid: string) {
  return await $authApi(`/client_profile/get/${uuid}`, {
    method: 'GET',
  })
}

export async function fuzzySearchClient(keyword: string): Promise<FuzzySearchResponse> {
  const res = await $authApi('/client_profile/fuzzy_search', {
    method: 'GET',
    params: { keyword },
  })

  return res as FuzzySearchResponse
}

export async function getClientProfileFromAquaAudit(companyNo: string): Promise<AquaAuditClientProfile> {
  const res = await $authApi('/aqua/audit/clientProfile/get', {
    method: 'GET',
    params: {
      company_no: companyNo,
    },
  })

  return res as AquaAuditClientProfile
}
