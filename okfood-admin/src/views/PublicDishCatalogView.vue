<script setup>
defineOptions({ name: 'PublicDishCatalogView' })
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { apiJson } from '../admin/core.js'

const route = useRoute()

/** @type {import('vue').Ref<{ dish_id: number, title?: string, desc?: string | null, price?: number | null, pic?: string | null, pic_thumb?: string | null, spice_label?: string, meat_category_name?: string | null, dish_type_category_id?: number | null, dish_type_category_name?: string | null }[]>} */
const items = ref([])
/** @type {import('vue').Ref<{ id: number | string, name: string }[]>} */
const typeFilters = ref([])
const storeName = ref('菜品库')
const storeLogo = ref('')
const loading = ref(true)
const loadError = ref('')
const query = ref('')
const activeType = ref('all')
/** @type {import('vue').Ref<typeof items.value[number] | null>} */
const detail = ref(null)
const detailOpen = ref(false)

const storeId = computed(() => {
  const raw = route.query.store_id ?? route.query.storeId ?? '1'
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return Number.isFinite(n) && n > 0 ? String(Math.trunc(n)) : '1'
})

const tenantId = computed(() => {
  const raw = route.query.tenant_id ?? route.query.tenantId ?? ''
  return String(Array.isArray(raw) ? raw[0] : raw).trim()
})

function publicHeaders() {
  /** @type {Record<string, string>} */
  const h = { 'X-Store-Id': storeId.value }
  if (tenantId.value) h['X-Tenant-Id'] = tenantId.value
  return h
}

const filteredItems = computed(() => {
  const q = query.value.trim().toLowerCase()
  return items.value.filter((d) => {
    if (activeType.value !== 'all' && String(d.dish_type_category_id) !== String(activeType.value)) {
      return false
    }
    if (!q) return true
    const hay = [d.title, d.desc, d.meat_category_name, d.dish_type_category_name]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    return hay.includes(q)
  })
})

function formatPrice(price) {
  if (price == null || price === '') return null
  const n = Number(price)
  if (!Number.isFinite(n)) return String(price)
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

function openDetail(dish) {
  detail.value = dish
  detailOpen.value = true
}

function closeDetail() {
  detailOpen.value = false
}

async function loadCatalog() {
  loading.value = true
  loadError.value = ''
  try {
    const headers = publicHeaders()
    const [catalog, storeInfo] = await Promise.all([
      apiJson('/api/menu/dishes', { headers }, { auth: false }),
      apiJson('/api/home/store-info', { headers }, { auth: false }).catch(() => null),
    ])
    items.value = Array.isArray(catalog?.items) ? catalog.items : []
    typeFilters.value = Array.isArray(catalog?.dish_type_filters) ? catalog.dish_type_filters : []
    if (storeInfo?.store_name) {
      storeName.value = String(storeInfo.store_name)
      document.title = `${storeInfo.store_name} · 菜品库`
    } else {
      document.title = '菜品库'
    }
    storeLogo.value = String(storeInfo?.store_logo_thumb_url || storeInfo?.store_logo_url || '').trim()
  } catch (e) {
    loadError.value = e instanceof Error ? e.message : '加载失败'
    items.value = []
  } finally {
    loading.value = false
  }
}

watch(storeId, () => {
  activeType.value = 'all'
  query.value = ''
  loadCatalog()
})

onMounted(loadCatalog)
</script>

<template>
  <div class="pdc">
    <header class="pdc-top">
      <img v-if="storeLogo" class="pdc-logo" :src="storeLogo" :alt="storeName" />
      <div v-else class="pdc-logo pdc-logo--fallback">{{ storeName.slice(0, 1) || '菜' }}</div>
      <div class="pdc-top-text">
        <div class="pdc-store">{{ storeName }}</div>
        <div class="pdc-sub">公开菜品库 · 无需登录</div>
      </div>
    </header>

    <section class="pdc-hero">
      <p class="pdc-kicker">Dish Catalog</p>
      <h1 class="pdc-title">{{ storeName }}</h1>
      <p class="pdc-desc">浏览门店全部在售菜品与简介</p>
      <div class="pdc-meta">
        <el-tag effect="plain" round>{{ items.length }} 道菜品</el-tag>
        <el-tag effect="plain" round type="success">公开浏览</el-tag>
      </div>
    </section>

    <div class="pdc-toolbar">
      <el-input
        v-model="query"
        clearable
        placeholder="搜索菜品名称或简介"
      />
      <div class="pdc-filters">
        <button
          type="button"
          class="pdc-chip"
          :class="{ 'is-active': activeType === 'all' }"
          @click="activeType = 'all'"
        >
          全部
        </button>
        <button
          v-for="f in typeFilters"
          :key="f.id"
          type="button"
          class="pdc-chip"
          :class="{ 'is-active': String(activeType) === String(f.id) }"
          @click="activeType = f.id"
        >
          {{ f.name }}
        </button>
      </div>
    </div>

    <div class="pdc-head">
      <h2>全部菜品</h2>
      <span>显示 {{ filteredItems.length }} / {{ items.length }}</span>
    </div>

    <div v-loading="loading" class="pdc-body">
      <el-empty v-if="!loading && loadError" :description="loadError">
        <el-button type="primary" @click="loadCatalog">重新加载</el-button>
      </el-empty>
      <el-empty v-else-if="!loading && !filteredItems.length" description="没有匹配的菜品" />
      <div v-else class="pdc-grid">
        <button
          v-for="d in filteredItems"
          :key="d.dish_id"
          type="button"
          class="pdc-card"
          @click="openDetail(d)"
        >
          <div class="pdc-card-media">
            <img
              v-if="d.pic_thumb || d.pic"
              :src="d.pic_thumb || d.pic"
              :alt="d.title || ''"
              loading="lazy"
            />
            <div v-else class="pdc-ph">暂无图片</div>
            <span v-if="d.spice_label" class="pdc-spice">{{ d.spice_label }}</span>
          </div>
          <div class="pdc-card-body">
            <div class="pdc-card-title">{{ d.title || '未命名菜品' }}</div>
            <div class="pdc-tags">
              <el-tag v-if="d.dish_type_category_name" size="small" effect="plain">
                {{ d.dish_type_category_name }}
              </el-tag>
              <el-tag v-if="d.meat_category_name" size="small" effect="plain" type="info">
                {{ d.meat_category_name }}
              </el-tag>
            </div>
            <div class="pdc-card-foot">
              <span v-if="formatPrice(d.price) != null" class="pdc-price">
                <small>¥</small>{{ formatPrice(d.price) }}
              </span>
              <span v-else class="pdc-price pdc-price--pending">价格待公布</span>
              <span class="pdc-more">详情</span>
            </div>
          </div>
        </button>
      </div>
    </div>

    <p class="pdc-note">仅供浏览展示 · 下单请前往小程序</p>

    <el-drawer
      v-model="detailOpen"
      direction="btt"
      size="auto"
      :with-header="false"
      class="pdc-drawer"
      @closed="detail = null"
    >
      <template v-if="detail">
        <div class="pdc-detail">
          <div class="pdc-detail-media">
            <img
              v-if="detail.pic || detail.pic_thumb"
              :src="detail.pic || detail.pic_thumb"
              :alt="detail.title || ''"
            />
            <div v-else class="pdc-ph pdc-ph--lg">暂无图片</div>
          </div>
          <h3 class="pdc-detail-title">{{ detail.title || '未命名菜品' }}</h3>
          <div class="pdc-detail-row">
            <span v-if="formatPrice(detail.price) != null" class="pdc-price pdc-price--lg">
              <small>¥</small>{{ formatPrice(detail.price) }}
            </span>
            <span v-else class="pdc-price pdc-price--pending">价格待公布</span>
            <el-tag v-if="detail.spice_label" size="small" type="warning" effect="plain">
              {{ detail.spice_label }}
            </el-tag>
            <el-tag v-if="detail.dish_type_category_name" size="small" effect="plain">
              {{ detail.dish_type_category_name }}
            </el-tag>
            <el-tag v-if="detail.meat_category_name" size="small" effect="plain" type="info">
              {{ detail.meat_category_name }}
            </el-tag>
          </div>
          <p class="pdc-detail-desc">{{ (detail.desc || '').trim() || '暂无更多介绍' }}</p>
          <el-button class="pdc-close-btn" @click="closeDetail">关闭</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.pdc {
  --ink: #1c2a22;
  --muted: #6b7c72;
  --leaf: #0e5a44;
  --leaf-soft: #ecfdf5;
  --paper: #f3f6f4;
  --line: rgba(14, 90, 68, 0.1);
  min-height: 100vh;
  color: var(--ink);
  background:
    radial-gradient(900px 420px at 8% -8%, #dceade 0%, transparent 55%),
    linear-gradient(180deg, #eef3ee 0%, var(--paper) 30%, #f7f8f5 100%);
  padding: 0 16px 40px;
  max-width: 1080px;
  margin: 0 auto;
  font-family: 'Plus Jakarta Sans', 'Noto Sans SC', 'PingFang SC', sans-serif;
}

.pdc-top {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 0 -16px;
  padding: 12px 16px;
  backdrop-filter: blur(12px);
  background: rgba(243, 246, 244, 0.9);
  border-bottom: 1px solid var(--line);
}

.pdc-logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  object-fit: cover;
  background: var(--leaf-soft);
  flex-shrink: 0;
}

.pdc-logo--fallback {
  display: grid;
  place-items: center;
  color: var(--leaf);
  font-weight: 800;
}

.pdc-store {
  font-weight: 800;
  font-size: 16px;
  line-height: 1.2;
}

.pdc-sub {
  font-size: 12px;
  color: var(--muted);
  margin-top: 2px;
}

.pdc-hero {
  margin: 18px 0 20px;
  padding: 24px 20px;
  border-radius: 24px;
  color: #f7faf7;
  background: linear-gradient(135deg, #0e5a44 0%, #1a7a5c 55%, #0b4635 100%);
  box-shadow: 0 12px 36px rgba(14, 90, 68, 0.18);
}

.pdc-kicker {
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.78;
  margin: 0 0 8px;
}

.pdc-title {
  margin: 0;
  font-size: clamp(26px, 6vw, 36px);
  font-weight: 900;
  line-height: 1.15;
}

.pdc-desc {
  margin: 10px 0 0;
  opacity: 0.88;
  font-size: 14px;
}

.pdc-meta {
  margin-top: 14px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pdc-meta :deep(.el-tag) {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.22);
  color: #fff;
}

.pdc-toolbar {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
  position: sticky;
  top: 61px;
  z-index: 15;
  padding: 8px 0 10px;
  background: linear-gradient(180deg, rgba(243, 246, 244, 0.96) 55%, rgba(243, 246, 244, 0));
}

.pdc-filters {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  scrollbar-width: none;
}

.pdc-filters::-webkit-scrollbar {
  display: none;
}

.pdc-chip {
  flex: 0 0 auto;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.75);
  color: #4a5c52;
  padding: 7px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.pdc-chip.is-active {
  background: var(--leaf);
  border-color: var(--leaf);
  color: #fff;
}

.pdc-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: 12px;
}

.pdc-head h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
}

.pdc-head span {
  font-size: 13px;
  color: var(--muted);
}

.pdc-body {
  min-height: 180px;
}

.pdc-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

@media (min-width: 720px) {
  .pdc-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }
}

@media (min-width: 980px) {
  .pdc-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }
}

.pdc-card {
  border: 0;
  background: rgba(255, 255, 255, 0.78);
  border-radius: 16px;
  overflow: hidden;
  text-align: left;
  cursor: pointer;
  padding: 0;
  box-shadow: 0 1px 0 var(--line);
  transition: transform 0.18s ease, box-shadow 0.18s ease;
}

.pdc-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 28px rgba(14, 90, 68, 0.1);
}

.pdc-card-media {
  position: relative;
  aspect-ratio: 1;
  background: #e7eee8;
}

.pdc-card-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.pdc-ph {
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  color: var(--muted);
  font-size: 13px;
}

.pdc-ph--lg {
  min-height: 180px;
}

.pdc-spice {
  position: absolute;
  left: 8px;
  bottom: 8px;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.92);
  color: #c45c26;
}

.pdc-card-body {
  padding: 12px;
}

.pdc-card-title {
  font-size: 15px;
  font-weight: 700;
  line-height: 1.35;
  min-height: 2.7em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.pdc-tags {
  margin-top: 6px;
  min-height: 22px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.pdc-card-foot {
  margin-top: 10px;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.pdc-price {
  color: var(--leaf);
  font-weight: 800;
  font-size: 18px;
}

.pdc-price small {
  font-size: 12px;
  margin-right: 1px;
}

.pdc-price--lg {
  font-size: 26px;
}

.pdc-price--pending {
  font-size: 12px;
  font-weight: 600;
  color: var(--muted);
}

.pdc-more {
  font-size: 12px;
  color: var(--muted);
}

.pdc-note {
  margin-top: 28px;
  text-align: center;
  font-size: 12px;
  color: var(--muted);
}

.pdc-detail {
  padding: 4px 4px 12px;
}

.pdc-detail-media {
  border-radius: 16px;
  overflow: hidden;
  aspect-ratio: 16 / 11;
  background: #e7eee8;
}

.pdc-detail-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.pdc-detail-title {
  margin: 14px 0 0;
  font-size: 24px;
  font-weight: 900;
  line-height: 1.25;
}

.pdc-detail-row {
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.pdc-detail-desc {
  margin: 16px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  color: #4a5c52;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 15px;
  line-height: 1.6;
}

.pdc-close-btn {
  width: 100%;
  margin-top: 18px;
}
</style>

<style>
/* 底部抽屉圆角：非 scoped，仅本页 class */
.pdc-drawer.el-drawer {
  border-radius: 20px 20px 0 0;
  max-height: 88vh;
}
</style>
