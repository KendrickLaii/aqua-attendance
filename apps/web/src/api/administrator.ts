import type { AdministratorFormData } from '@/components/dialogs/tax/AdministratorDialog.vue'

export async function createAdministrator(formData: AdministratorFormData) {
    const res = await $authApi('/admin/create',{
        method: 'POST',
        body: formData,
    })
    return res
}

export async function getAllAdministrators(page:number, size:number) {
    const res = await $authApi('/admin/get/all',{
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

export async function updateAdministrator(formData: AdministratorFormData) {
    const res = await $authApi('/admin/edit',{
        method: 'PUT',
        body: formData,
    })
    return res
}

export async function deleteAdministrator(uuid: string) {
    const res = await $authApi('/admin/del',{
        method: 'DELETE',
        body: {
            uuid: uuid,
            data:[`${uuid}`] //update this if handle batch delete
        },
    })
    return res
}
