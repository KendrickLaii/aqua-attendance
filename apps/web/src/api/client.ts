import type { AquaAuditClientProfile, Content, FuzzySearchResponse } from '@/types/client'

export async function createClient(formData: Content) {
    const res = await $authApi('/client_profile/create',{
        method: 'POST',
        body: formData,
    })
    return res
}

export async function getAllClients(page:number, size:number) {
    const res = await $authApi('/client_profile/get/all',{
        method: 'GET',
        params: {
            page: page,
            size: size,
        },
        onResponseError({ response }) {
            console.log(response._data.errors)
        },
    })
    return res
}

export async function updateClient(formData: Partial<Content>) {
    const res = await $authApi('/client_profile/edit',{
        method: 'PUT',
        body: formData,
    })
    return res
}

export async function deleteClient(uuid: string) {
    const res = await $authApi('/client_profile/del',{
        method: 'DELETE',
        body: {
            uuid: uuid,
            data:[`${uuid}`] //update this if handle batch delete
        },
    })
    return res
}

export async function searchClientByCompanyNumberAndYearOfAssessment(companyNo: string, yearOfAssessment: string) {
    const res = await $authApi('/client_profile/search', {
        method: 'GET',
        params: {
            company_no: companyNo,
            year_of_assessment: yearOfAssessment,
        },
    })
    return res
}

export async function getClientByUuid(uuid: string) {
    const res = await $authApi(`/client_profile/get/${uuid}`, {
        method: 'GET',
    })
    return res
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
