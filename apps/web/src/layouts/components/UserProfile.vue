<script setup lang="ts">
import { PerfectScrollbar } from 'vue3-perfect-scrollbar'
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'
import { isAttendanceLoggedIn } from '@/utils/attendanceSession'

const router = useRouter()
const ability = useAbility()
const attendanceAuth = useAttendanceAuthStore()

// TODO: Get type from backend
const userData = useCookie<any>('userData')

const logout = async () => {
  const onAttendanceApp =
    router.currentRoute.value.path.startsWith('/attendance')
    || isAttendanceLoggedIn()

  if (onAttendanceApp) {
    attendanceAuth.logout()
    ability.update([])
    await router.push({ name: 'attendance-login' })
    return
  }

  useCookie('accessToken').value = null
  userData.value = null
  await router.push('/login')
  useCookie('userAbilityRules').value = null
  ability.update([])
}

const userProfileList = [
  { type: 'divider' },
  {
    type: 'navItem',
    icon: 'ri-user-line',
    title: 'Profile',
    to: { name: 'apps-user-view-id', params: { id: 21 } },
  },
  {
    type: 'navItem',
    icon: 'ri-settings-4-line',
    title: 'Settings',
    to: { name: 'pages-account-settings-tab', params: { tab: 'account' } },
  },
  // {
  //   type: 'navItem',
  //   icon: 'ri-file-text-line',
  //   title: 'Billing Plan',
  //   to: { name: 'pages-account-settings-tab', params: { tab: 'billing-plans' } },
  //   badgeProps: { color: 'error', content: '4' },
  // },
  // { type: 'divider' },
  // {
  //   type: 'navItem',
  //   icon: 'ri-money-dollar-circle-line',
  //   title: 'Pricing',
  //   to: { name: 'pages-pricing' },
  // },
  {
    type: 'navItem',
    icon: 'ri-question-line',
    title: 'FAQ',
    to: { name: 'pages-faq' },
  },
  { type: 'divider' },

]
</script>

<template>
  <VBadge
    v-if="userData"
    dot
    bordered
    location="bottom right"
    offset-x="3"
    offset-y="3"
    color="success"
  >
    <VAvatar
      class="cursor-pointer"
      size="38"
      :color="!(userData && userData.avatar) ? 'primary' : undefined"
      :variant="!(userData && userData.avatar) ? 'tonal' : undefined"
    >
      <VImg
        v-if="userData && userData.avatar"
        :src="userData.avatar"
      />
      <VIcon
        v-else
        icon="ri-user-line"
      />

      <!-- SECTION Menu -->
      <VMenu
        activator="parent"
        width="230"
        location="bottom end"
        offset="15px"
      >
        <VList>
          <VListItem>
            <div class="d-flex gap-2 align-center">
              <VListItemAction>
                <VBadge
                  dot
                  location="bottom right"
                  offset-x="3"
                  offset-y="3"
                  color="success"
                >
                  <VAvatar
                    :color="!(userData && userData.avatar) ? 'primary' : undefined"
                    :variant="!(userData && userData.avatar) ? 'tonal' : undefined"
                  >
                    <VImg
                      v-if="userData && userData.avatar"
                      :src="userData.avatar"
                    />
                    <VIcon
                      v-else
                      icon="ri-user-line"
                    />
                  </VAvatar>
                </VBadge>
              </VListItemAction>

              <div>
                <h6 class="text-h6 font-weight-medium">
                  {{ userData.fullName || userData.username }}
                </h6>
                <VListItemSubtitle class="text-capitalize text-disabled">
                  {{ userData.role }}
                </VListItemSubtitle>
              </div>
            </div>
          </VListItem>

          <PerfectScrollbar :options="{ wheelPropagation: false }">
            <template
              v-for="item in userProfileList"
              :key="item.title"
            >
              <VListItem
                v-if="item.type === 'navItem'"
                :to="item.to"
              >
                <template #prepend>
                  <VIcon
                    :icon="item.icon"
                    size="22"
                  />
                </template>

                <VListItemTitle>{{ item.title }}</VListItemTitle>

                <template
                  v-if="item.badgeProps"
                  #append
                >
                  <VBadge
                    inline
                    v-bind="item.badgeProps"
                  />
                </template>
              </VListItem>

              <VDivider
                v-else
                class="my-1"
              />
            </template>

            <VListItem>
              <VBtn
                block
                color="error"
                size="small"
                append-icon="ri-logout-box-r-line"
                @click="logout"
              >
                Logout
              </VBtn>
            </VListItem>
          </PerfectScrollbar>
        </VList>
      </VMenu>
      <!-- !SECTION -->
    </VAvatar>
  </VBadge>
</template>
