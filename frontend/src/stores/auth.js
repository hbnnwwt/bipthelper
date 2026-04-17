import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from '../api'

export const useAuthStore = defineStore('auth', () => {
  // token 不再存储在 localStorage（已迁移到 httpOnly cookie）
  const token = ref('')  // 仅保留空值，不再读取 localStorage
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))
  const points = ref(Number(localStorage.getItem('points') || '0'))
  const lastCheckinDate = ref(localStorage.getItem('lastCheckinDate') || null)
  // tokenExpiry 用于检测 localStorage 中是否有残留的过期会话
  const tokenExpiry = ref(Number(localStorage.getItem('tokenExpiry') || '0'))
  const nickname = ref(localStorage.getItem('nickname') || null)
  const phone = ref(localStorage.getItem('phone') || null)
  const avatarUrl = ref(localStorage.getItem('avatarUrl') || null)

  // isLoggedIn 依赖 user 和 tokenExpiry（而非 token 值本身）
  const isLoggedIn = computed(() => !!user.value && Date.now() < tokenExpiry.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setAuth(newToken, newUser, expiresAt, newPoints = 0, newLastCheckinDate = null) {
    user.value = newUser
    // 使用传入的过期时间，或默认 7 天（与 httpOnly cookie 过期时间一致）
    tokenExpiry.value = expiresAt || (Date.now() + 7 * 24 * 60 * 60 * 1000)
    localStorage.setItem('user', JSON.stringify(newUser))
    localStorage.setItem('tokenExpiry', String(tokenExpiry.value))
    // 不再存储 token 到 localStorage（由 httpOnly cookie 处理）
    // 不再设置 Authorization header（由 httpOnly cookie 自动发送）
    points.value = newPoints
    lastCheckinDate.value = newLastCheckinDate
    if (newUser) {
      nickname.value = newUser.nickname || null
      phone.value = newUser.phone || null
      avatarUrl.value = newUser.avatar_url || null
      localStorage.setItem('nickname', nickname.value || '')
      localStorage.setItem('phone', phone.value || '')
      localStorage.setItem('avatarUrl', avatarUrl.value || '')
    }
    localStorage.setItem('points', String(newPoints))
    if (newLastCheckinDate) {
      localStorage.setItem('lastCheckinDate', newLastCheckinDate)
    }
  }

  async function logout() {
    try {
      await axios.post('/auth/logout')
    } catch (e) {
      // cookie 清除失败不影响本地登出
    }
    token.value = ''
    user.value = null
    tokenExpiry.value = 0
    points.value = 0
    lastCheckinDate.value = null
    localStorage.removeItem('user')
    localStorage.removeItem('tokenExpiry')
    localStorage.removeItem('points')
    localStorage.removeItem('lastCheckinDate')
    nickname.value = null
    phone.value = null
    avatarUrl.value = null
    localStorage.removeItem('nickname')
    localStorage.removeItem('phone')
    localStorage.removeItem('avatarUrl')
  }

  async function syncFromServer() {
    if (!user.value) return
    try {
      const { data } = await axios.get('/auth/me')
      points.value = data.points ?? 0
      lastCheckinDate.value = data.last_checkin_date || null
      localStorage.setItem('points', String(points.value))
      if (lastCheckinDate.value) localStorage.setItem('lastCheckinDate', lastCheckinDate.value)
      if (data.user) {
        nickname.value = data.user.nickname || null
        phone.value = data.user.phone || null
        avatarUrl.value = data.user.avatar_url || null
        localStorage.setItem('nickname', nickname.value || '')
        localStorage.setItem('phone', phone.value || '')
        localStorage.setItem('avatarUrl', avatarUrl.value || '')
      }
    } catch {
      // 401 等 → 拦截器会处理跳转
    }
  }

  // 如果 user 存在且未过期，认为已登录（否则清除）
  if (!user.value || Date.now() >= tokenExpiry.value) {
    user.value = null
    tokenExpiry.value = 0
  }

  return { token, user, points, lastCheckinDate, nickname, phone, avatarUrl, isLoggedIn, isAdmin, setAuth, logout, syncFromServer }
})
