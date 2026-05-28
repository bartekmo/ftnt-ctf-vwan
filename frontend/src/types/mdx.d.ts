/// <reference types="vite/client" />

declare module '*.mdx' {
  import type { ComponentType } from 'react'
  export const frontmatter: Record<string, unknown>
  const Component: ComponentType
  export default Component
}

declare module '*?raw' {
  const content: string
  export default content
}

// Type declaration for direct YAML imports
declare module '*.yaml' {
  const content: Record<string, unknown>
  export default content
}
declare module '*.yml' {
  const content: Record<string, unknown>
  export default content
}
