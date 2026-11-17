const KEY = "pending_invite_token";

/** The invitation token arrives in the URL fragment; keep it for the login/sign-up round trip, in this tab only. */
export const rememberInvite = (token: string) => sessionStorage.setItem(KEY, token);
export const pendingInvite = () => sessionStorage.getItem(KEY);
export const clearInvite = () => sessionStorage.removeItem(KEY);
