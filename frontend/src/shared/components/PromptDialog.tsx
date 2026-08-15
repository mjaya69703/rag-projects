import React, { useEffect, useState } from 'react'
import { Button } from './Button'
import { Modal } from './Modal'

interface PromptDialogProps {
  isOpen: boolean
  title: string
  label?: string
  placeholder?: string
  defaultValue?: string
  confirmText?: string
  cancelText?: string
  loading?: boolean
  onConfirm: (value: string) => void
  onCancel: () => void
}

export const PromptDialog: React.FC<PromptDialogProps> = ({
  isOpen,
  title,
  label,
  placeholder,
  defaultValue = '',
  confirmText = 'Simpan',
  cancelText = 'Batal',
  loading = false,
  onConfirm,
  onCancel,
}) => {
  const [value, setValue] = useState(defaultValue)

  useEffect(() => {
    setValue(defaultValue)
  }, [defaultValue, isOpen])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (value.trim()) {
      onConfirm(value.trim())
    }
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onCancel}
      title={title}
      maxWidth="sm"
      footer={
        <>
          <Button variant="ghost" onClick={onCancel} disabled={loading}>
            {cancelText}
          </Button>
          <Button variant="primary" onClick={handleSubmit} loading={loading} disabled={!value.trim()}>
            {confirmText}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="prompt-dialog__form">
        {label && <label className="form-label">{label}</label>}
        <input
          type="text"
          className="form-input"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder={placeholder}
          autoFocus
          disabled={loading}
        />
      </form>
    </Modal>
  )
}
