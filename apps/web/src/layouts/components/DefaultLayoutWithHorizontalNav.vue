<script lang="ts" setup>
import { h } from 'vue'
import { useTheme } from 'vuetify'
import navItems from '@/navigation/horizontal'
import { applyBrandPrimaryColor, loadBranding, useBranding } from '@/composables/useBranding'

import { themeConfig } from '@themeConfig'

// Components
import Footer from '@/layouts/components/Footer.vue'
import NavBarNotifications from '@/layouts/components/NavBarNotifications.vue'
import NavSearchBar from '@/layouts/components/NavSearchBar.vue'
import NavbarShortcuts from '@/layouts/components/NavbarShortcuts.vue'
import NavbarThemeSwitcher from '@/layouts/components/NavbarThemeSwitcher.vue'
import UserProfile from '@/layouts/components/UserProfile.vue'
import NavBarI18n from '@core/components/I18n.vue'
import { HorizontalNavLayout } from '@layouts'
import { VNodeRenderer } from '@layouts/components/VNodeRenderer'

const { brand } = useBranding()

loadBranding()

// Runtime brand primary-color override (aqua has none → identical to before)
const vTheme = useTheme()

watch(brand, b => {
  if (b.primaryColor)
    applyBrandPrimaryColor(vTheme, b.primaryColor)
})

// Aqua keeps the themeConfig navbar title/logo untouched (parity); other
// brands render their registry values.
const appTitle = computed(() => (brand.value.key === 'aqua' ? themeConfig.app.title : brand.value.title))

const appLogo = computed(() =>
  brand.value.key === 'aqua'
    ? themeConfig.app.logo
    : h('img', { src: brand.value.logo, style: 'height: 30px; width: auto;' }))
</script>

<template>
  <HorizontalNavLayout :nav-items="navItems">
    <!-- 👉 navbar -->
    <template #navbar>
      <RouterLink
        to="/"
        class="d-flex align-start gap-x-4"
      >
        <VNodeRenderer :nodes="appLogo" />

        <h1 class="leading-normal text-xl text-uppercase">
          {{ appTitle }}
        </h1>
      </RouterLink>
      <VSpacer />

      <NavSearchBar />

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
    </template>

    <!-- 👉 Pages -->
    <slot />

    <!-- 👉 Footer -->
    <template #footer>
      <Footer />
    </template>

    <!-- 👉 Customizer -->
    <TheCustomizer />
  </HorizontalNavLayout>
</template>
