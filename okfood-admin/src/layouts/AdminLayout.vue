<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import {
  Users,
  Truck,
  Utensils,
  BarChart3,
  MapPin,
  DollarSign,
  LogOut,
  ClipboardList,
} from 'lucide-vue-next'
import { handleAdminLogout } from '../admin/core.js'

const route = useRoute()

const pageTitle = computed(() => route.meta.title || 'OK Fine Admin')

const activeMenuPath = computed(() => route.path)
</script>

<template>
  <div class="admin-layout">
    <aside class="sidebar">
      <div class="logo-area">
        <div class="logo-box">&#128076;</div>
        <div class="logo-text">
          <h1>OK Fine</h1>
          <span>SUPER ADMIN</span>
        </div>
      </div>

      <el-menu
        class="sidebar-menu"
        :default-active="activeMenuPath"
        router
        :ellipsis="false"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.72)"
        active-text-color="#facc15"
      >
        <el-menu-item index="/dashboard">
          <span class="menu-item-inner">
            <BarChart3 :size="18" stroke-width="2" />
            <span>营业概览</span>
          </span>
        </el-menu-item>
        <el-menu-item index="/users">
          <span class="menu-item-inner">
            <Users :size="18" stroke-width="2" />
            <span>会员档案</span>
          </span>
        </el-menu-item>
        <el-menu-item index="/card-orders">
          <span class="menu-item-inner">
            <ClipboardList :size="18" stroke-width="2" />
            <span>开卡工单</span>
          </span>
        </el-menu-item>
        <el-menu-item index="/delivery">
          <span class="menu-item-inner">
            <Truck :size="18" stroke-width="2" />
            <span>配送大表</span>
          </span>
        </el-menu-item>

        <el-sub-menu index="sub-delivery">
          <template #title>
            <span class="menu-item-inner">
              <MapPin :size="18" stroke-width="2" />
              <span>配送管理</span>
            </span>
          </template>
          <el-menu-item index="/regions">配送区域管理</el-menu-item>
          <el-menu-item index="/couriers">配送员管理</el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/finance">
          <span class="menu-item-inner">
            <DollarSign :size="18" stroke-width="2" />
            <span>财务中心</span>
          </span>
        </el-menu-item>

        <el-sub-menu index="sub-menu-mgmt">
          <template #title>
            <span class="menu-item-inner">
              <Utensils :size="18" stroke-width="2" />
              <span>菜单管理</span>
            </span>
          </template>
          <el-menu-item index="/menu">菜品管理</el-menu-item>
          <el-menu-item index="/weekly-menu">本周菜单</el-menu-item>
        </el-sub-menu>
      </el-menu>

      <button type="button" class="sidebar-footer" @click="handleAdminLogout">
        <div class="admin-info">
          <div class="avatar">Admin</div>
          <span>安全退出</span>
        </div>
        <LogOut :size="16" />
      </button>
    </aside>

    <main class="main-body">
      <header class="top-header">
        <div class="title-wrap">
          <div class="live-indicator">
            <span class="dot"></span> System Live · New Xiang
          </div>
          <h2 class="page-title">{{ pageTitle }}</h2>
        </div>
      </header>

      <router-view />
    </main>
  </div>
</template>
