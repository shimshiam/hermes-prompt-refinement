// Stand-in for `@hermes/plugin-sdk` in the standalone tests. It exposes only
// what the pure-logic modules touch; tests that need more mock it themselves.
export { atom, computed } from 'nanostores'

export const host = {}
export const COMPOSER_AREAS = { actions: 'composer.actions', middleware: 'composer.middleware', top: 'composer.top' }
