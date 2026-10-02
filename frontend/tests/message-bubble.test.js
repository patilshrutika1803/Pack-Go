import assert from 'node:assert/strict'
import test from 'node:test'
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

test('message displays retrieved source citation details', async () => {
  const server = await createServer({
    configFile: fileURLToPath(new URL('../vite.config.js', import.meta.url)),
    root: fileURLToPath(new URL('..', import.meta.url)),
    optimizeDeps: { noDiscovery: true, include: [] },
    ssr: { noExternal: ['dompurify'] },
    server: { middlewareMode: true },
    appType: 'custom',
    plugins: [{
      name: 'mock-dompurify-for-server-render',
      enforce: 'pre',
      resolveId(id) {
        return id === 'dompurify' ? '\0mock-dompurify' : null
      },
      load(id) {
        return id === '\0mock-dompurify' ? 'export default { sanitize: value => value }' : null
      },
    }],
  })

  try {
    const { default: MessageBubble } = await server.ssrLoadModule('/src/components/MessageBubble.jsx')
    const markup = renderToStaticMarkup(createElement(MessageBubble, {
      message: {
        role: 'assistant',
        content: 'North Goa beaches include Keri and Arambol.',
        sources: [{
          document_id: 'goa-guide',
          filename: 'goa-guide.pdf',
          page: 2,
          chunk_index: 1,
          destination: 'Goa',
          category: 'travel_guide',
          preview: 'North Goa beaches include Keri and Arambol.',
        }],
      },
    }))

    assert.match(markup, /Sources/)
    assert.match(markup, /goa-guide\.pdf/)
    assert.match(markup, /Page 2/)
    assert.match(markup, /North Goa beaches include Keri and Arambol\./)
  } finally {
    await server.close()
  }
})