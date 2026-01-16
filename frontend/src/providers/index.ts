/**
 * Data providers — global application state.
 *
 * These providers manage data that is needed across the app.
 * Only the top-level page should connect to these contexts,
 * then pass data down to components via props.
 */

export { AuthProvider, useAuth } from "./auth-provider"
export { ChatsProvider, useChatsContext } from "./chats-provider"
