import type { AdministratorFormData } from '@/components/dialogs/tax/AdministratorDialog.vue'

export async function createAdministrator(formData: AdministratorFormData) {
  return await $authApi('/admin/create', {
    method: 'POST',
    body: formData,
  })
}

export async function getAllAdministrators(page: number, size: number) {
  return await $authApi('/admin/get/all', {
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

export async function updateAdministrator(formData: AdministratorFormData) {
  return await $authApi('/admin/edit', {
    method: 'PUT',
    body: formData,
  })
}

export async function deleteAdministrator(uuid: string) {
  return await $authApi('/admin/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [`${uuid}`], // update this if handle batch delete
    },
  })
}
