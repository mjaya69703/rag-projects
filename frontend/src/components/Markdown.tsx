import { memo, useMemo } from 'react'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js/lib/core'
import javascript from 'highlight.js/lib/languages/javascript'
import typescript from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import bash from 'highlight.js/lib/languages/bash'
import json from 'highlight.js/lib/languages/json'
import xml from 'highlight.js/lib/languages/xml'
import css from 'highlight.js/lib/languages/css'
import java from 'highlight.js/lib/languages/java'
import cpp from 'highlight.js/lib/languages/cpp'
import sql from 'highlight.js/lib/languages/sql'
import yaml from 'highlight.js/lib/languages/yaml'
import { marked } from 'marked'

// Daftar bahasa umum — jangan import highlight.js full (hemat ~300KB).
hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', bash)
hljs.registerLanguage('json', json)
hljs.registerLanguage('xml', xml)
hljs.registerLanguage('html', xml)
hljs.registerLanguage('css', css)
hljs.registerLanguage('java', java)
hljs.registerLanguage('cpp', cpp)
hljs.registerLanguage('c', cpp)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('yaml', yaml)

marked.setOptions({ breaks: true, gfm: true })

/** Render markdown (output LLM = data tak tepercaya → WAJIB sanitasi). */
export const Markdown = memo(function Markdown({ content }: { content: string }) {
  const html = useMemo(() => {
    if (!content) return ''
    let raw = ''
    try {
      raw = marked.parse(content, { async: false }) as string
    } catch {
      raw = ''
    }
    if (!raw) {
      const div = document.createElement('div')
      div.textContent = content
      raw = div.innerHTML.replace(/\n/g, '<br>')
    }
    return DOMPurify.sanitize(raw)
  }, [content])

  return (
    <div
      className="message-text"
      dangerouslySetInnerHTML={{ __html: html }}
      ref={(node) => {
        if (node) node.querySelectorAll('pre code').forEach((block) => hljs.highlightElement(block as HTMLElement))
      }}
    />
  )
})
