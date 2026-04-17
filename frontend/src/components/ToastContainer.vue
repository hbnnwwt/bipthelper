<template>
  <Teleport to="body">
    <div class="toast-container" aria-live="polite">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="toast"
          :class="`toast-${toast.type}`"
          role="alert"
        >
          <svg v-if="toast.type === 'success'" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M16 8A8 8 0 110 8a8 8 0 0116 0zm-3.97-3.03a.75.75 0 00-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 00-1.06 1.06L6.97 11.03a.75.75 0 001.079-.02l3.992-4.99a.75.75 0 00-.01-1.05z"/>
          </svg>
          <svg v-else-if="toast.type === 'error'" width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm8-3a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 018 5zm0 8a1 1 0 110-2 1 1 0 010 2z"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="currentColor">
            <path d="M8 16A8 8 0 108 0a8 8 0 000 16zm.75-11.25v4.5a.75.75 0 01-1.5 0v-4.5a.75.75 0 011.5 0zm0 7a1 1 0 11-2 0 1 1 0 012 0z"/>
          </svg>
          <span class="toast-message">{{ toast.message }}</span>
          <button class="toast-close" @click="remove(toast.id)" aria-label="关闭">&times;</button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast } from '../composables/toast'

const { toasts, remove } = useToast()
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: var(--space-4);
  right: var(--space-4);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-width: 380px;
}

.toast {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-lg);
  font-size: 0.875rem;
  font-weight: 500;
  box-shadow: var(--shadow-lg);
  animation: toast-in 0.3s ease;
}

.toast-success {
  background: var(--toast-success-bg);
  color: var(--toast-success-text);
  border: 1px solid var(--toast-success-border);
}

.toast-error {
  background: var(--toast-error-bg);
  color: var(--toast-error-text);
  border: 1px solid var(--toast-error-border);
}

.toast-info {
  background: var(--toast-info-bg);
  color: var(--toast-info-text);
  border: 1px solid var(--toast-info-border);
}

.toast-message {
  flex: 1;
  line-height: 1.4;
}

.toast-close {
  background: none;
  border: none;
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  opacity: 0.5;
  padding: 0;
  color: inherit;
}

.toast-close:hover { opacity: 1; }

.toast-enter-active,
.toast-leave-active { transition: all 0.3s ease; }
.toast-enter-from { transform: translateX(100%); opacity: 0; }
.toast-leave-to { transform: translateX(100%); opacity: 0; }

@keyframes toast-in {
  from { transform: translateX(100%); opacity: 0; }
  to { transform: translateX(0); opacity: 1; }
}
</style>
