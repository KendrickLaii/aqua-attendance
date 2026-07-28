import type { Content, HeadlinesProperties } from '@/types/headlines'

export type HeadlinesFormData = Partial<Content> & {
  title?: string | null
}

export async function getAllHeadlines(): Promise<HeadlinesProperties> {
  const res = await $authApi('/headlines/get/all', {
    method: 'GET',
  })

  return res as HeadlinesProperties
}

export async function createHeadlines(formData: HeadlinesFormData) {
  return await $authApi('/headlines/create', {
    method: 'POST',
    body: formData,
  })
}

export async function updateHeadlines(formData: HeadlinesFormData) {
  return await $authApi('/headlines/edit', {
    method: 'PUT',
    body: formData,
  })
}

export async function deleteHeadlines(uuid: string) {
  return await $authApi('/headlines/del', {
    method: 'DELETE',
    body: {
      uuid,
      data: [uuid],
    },
  })
}
