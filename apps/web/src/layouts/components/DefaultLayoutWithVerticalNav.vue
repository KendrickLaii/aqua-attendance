<script lang="ts" setup>
import { useTheme } from 'vuetify'
import rawNavItems, { filterNavByFeatures } from '@/navigation/vertical'
import { loadFeatureFlags, useFeatureFlags } from '@/composables/useFeatureFlags'
import { applyBrandPrimaryColor, loadBranding, useBranding } from '@/composables/useBranding'
import { themeConfig } from '@themeConfig'
import { useAttendanceAuthStore } from '@/stores/useAttendanceAuthStore'

// Components
import Footer from '@/layouts/components/Footer.vue'
import NavBarNotifications from '@/layouts/components/NavBarNotifications.vue'
import NavSearchBar from '@/layouts/components/NavSearchBar.vue'
import NavbarShortcuts from '@/layouts/components/NavbarShortcuts.vue'
import NavbarThemeSwitcher from '@/layouts/components/NavbarThemeSwitcher.vue'
import UserProfile from '@/layouts/components/UserProfile.vue'
import NavBarI18n from '@core/components/I18n.vue'

// @layouts plugin
import { VerticalNavLayout } from '@layouts'

const { featureFlags } = useFeatureFlags()
const { brand, applyNavTitles, t } = useBranding()

loadFeatureFlags()
loadBranding()

// Runtime brand primary-color override (aqua has none → identical to before)
const vTheme = useTheme()

watch(brand, b => {
  if (b.primaryColor)
    applyBrandPrimaryColor(vTheme, b.primaryColor)
})

const navItems = computed(() =>
  applyNavTitles(filterNavByFeatures(rawNavItems, featureFlags.value, brand.value.hiddenRoutes)))

const auth = useAttendanceAuthStore()
const needsTeam = computed(() => {
  const role = auth.role
  if (role !== 'admin' && role !== 'user')
    return false

  return !(auth.user?.location_ids?.length)
})
</script>

<template>
  <VerticalNavLayout :nav-items="navItems">
    <VAlert
      v-if="needsTeam"
      type="warning"
      variant="tonal"
      class="ma-4"
      :text="t('未指派地點，請聯絡 superadmin')"
    />
    <!-- 👉 navbar -->
    <template #navbar="{ toggleVerticalOverlayNavActive }">
      <div class="d-flex h-100 align-center">
        <IconBtn
          id="vertical-nav-toggle-btn"
          class="ms-n2 d-lg-none"
          @click="toggleVerticalOverlayNavActive(true)"
        >
          <VIcon icon="ri-menu-line" />
        </IconBtn>

        <NavSearchBar class="ms-lg-n2" />

        <VSpacer />

        <!--
          <NavBarI18n
          v-if="themeConfig.app.i18n.enable && themeConfig.app.i18n.langConfig?.length"
          :languages="themeConfig.app.i18n.langConfig"
          />
        -->
        <NavbarThemeSwitcher />
        <NavbarShortcuts />
        <!-- <NavBarNotifications class="me-2" /> -->
        <UserProfile />
      </div>
    </template>

    <!-- 👉 Pages -->
    <slot />

    <!-- 👉 Footer -->
    <template #footer>
      <Footer />
    </template>

    <!-- 👉 Customizer -->
    <TheCustomizer />
  </VerticalNavLayout>
</template>
