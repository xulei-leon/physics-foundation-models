import { readdirSync, readFileSync } from 'node:fs'
import { basename, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import { defineConfig } from 'vitepress'

const docsRoot = fileURLToPath(new URL('..', import.meta.url))

function humanize(name) {
  return name.replace(/[-_]+/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function pageTitle(path) {
  const heading = readFileSync(path, 'utf8').match(/^#\s+(.+)$/m)?.[1]
  return heading?.replace(/[`*_]/g, '') ?? humanize(basename(path, '.md'))
}

function pageLink(path) {
  const route = relative(docsRoot, path).split(sep).join('/').replace(/\.md$/, '')
  return route === 'index' ? '/' : `/${route.replace(/\/index$/, '')}`
}

export function createSidebar(directory = docsRoot) {
  return readdirSync(directory, { withFileTypes: true })
    .filter((entry) => !entry.name.startsWith('.') && (entry.isDirectory() || entry.name.endsWith('.md')))
    .sort((left, right) => left.name.localeCompare(right.name))
    .flatMap((entry) => {
      const path = join(directory, entry.name)
      if (!entry.isDirectory()) return [{ text: pageTitle(path), link: pageLink(path) }]

      const items = createSidebar(path)
      return items.length ? [{ text: humanize(entry.name), collapsed: false, items }] : []
    })
}

export default defineConfig({
  title: 'particleML',
  description: 'Blinded ATLAS Open Data four-lepton Higgs ML analysis documentation.',
  base: '/particleML/',
  cleanUrls: true,
  themeConfig: {
    nav: [
      { text: 'Home', link: '/' },
      { text: 'GitHub', link: 'https://github.com/xulei-leon/particleML' }
    ],
    sidebar: createSidebar(),
    search: { provider: 'local' },
    socialLinks: [{ icon: 'github', link: 'https://github.com/xulei-leon/particleML' }]
  }
})
