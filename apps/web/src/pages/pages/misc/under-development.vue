<script setup lang="ts">
import miscMaskDark from '@images/misc/misc-mask-dark.png'
import miscMaskLight from '@images/misc/misc-mask-light.png'
import tree1 from '@images/misc/tree1.png'

const authThemeMask = useGenerateImageVariant(miscMaskLight, miscMaskDark)

</script>

<template>
  <div class="misc-wrapper d-flex flex-column align-center justify-center h-100">
    <div class="text-center mb-10">
      <!-- 👉 Title and subtitle -->
      <h4 class="text-h4 mb-2">
        Under Development! 🚧
      </h4>
      <p class="mb-0 text-body-1">
        Sorry for the inconvenience but we're performing some development at the moment
      </p>
      <VBtn
        to="/"
        class="mt-10"
        style="z-index: 1;"
      >
        Back to Home
      </VBtn>
    </div>

    <img
      height="210"
      :src="tree1"
      class="misc-footer-tree-1 d-none d-md-block"
    >
    <img
      cover
      :src="authThemeMask"
      height="172"
      class="misc-footer-img d-none d-md-block flip-in-rtl"
    >
  </div>
</template>

<style lang="scss">
@use "@core/scss/template/pages/misc.scss";
.misc-wrapper{
    height: 80dvh !important;
}
.misc-footer-tree-1{
    position: absolute;
        bottom: 10vh;
        right: 10vh;
}
.misc-footer-img{
    position: absolute;
    bottom: 10vh;
}
</style>
