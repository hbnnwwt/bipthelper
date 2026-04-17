import { ref } from 'vue'

const toasts = ref([])
let id = 0

export function useToast() {
  function add(message, type = 'info', duration = 3000) {
    const toastId = ++id
    toasts.value.push({ id: toastId, message, type })
    if (duration > 0) {
      setTimeout(() => remove(toastId), duration)
    }
  }

  function remove(toastId) {
    const idx = toasts.value.findIndex(t => t.id === toastId)
    if (idx !== -1) toasts.value.splice(idx, 1)
  }

  function success(message) { add(message, 'success') }
  function error(message) { add(message, 'error', 5000) }
  function info(message) { add(message, 'info') }

  return { toasts, success, error, info, remove }
}
