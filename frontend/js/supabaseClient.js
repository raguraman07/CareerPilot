// CareerPilot AI - Supabase JS Client Initialization
// Imported via CDN as an ES Module.
import { createClient } from 'https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/+esm';

// IMPORTANT SECURITY WARNING:
// 1. Use ONLY the public 'anon' key on the client side.
// 2. NEVER expose the 'service_role' key in any frontend code.
//
// Replace these placeholders with your actual Supabase Project credentials:
const SUPABASE_URL = 'https://aekuesezmlpjquttztwu.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_xy-jZMcTkwD8V6GniJCpzw_wCkJgSv9';

// Initialize the Supabase Client with session persistence and auto-refresh configuration
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
    auth: {
        persistSession: true,
        autoRefreshToken: true,
        detectSessionInUrl: true,
        storage: window.localStorage
    }
});

