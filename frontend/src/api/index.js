import axios from 'axios'

const CRAWLER_API = 'http://localhost:8001'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  withCredentials: true, // 发送 cookies 到同源后端
})

const crawlerApi = axios.create({
  baseURL: CRAWLER_API + '/admin',
  timeout: 30000,
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export { CRAWLER_API, crawlerApi }
export default api
