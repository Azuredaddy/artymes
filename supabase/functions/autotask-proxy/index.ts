// Supabase Edge Function — Autotask API Proxy
// Deploy: supabase functions deploy autotask-proxy
// This function proxies requests to Autotask REST API, handling CORS for the browser.

import { serve } from "https://deno.land/std@0.190.0/http/server.ts"

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
}

interface ProxyRequest {
  endpoint: string
  method: "GET" | "POST" | "PATCH"
  body?: unknown
  credentials: {
    username: string
    secret: string
    integrationCode: string
    zoneUrl: string
  }
}

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders })
  }

  try {
    const { endpoint, method, body, credentials }: ProxyRequest = await req.json()
    const { username, secret, integrationCode, zoneUrl } = credentials

    if (!username || !secret || !integrationCode || !zoneUrl) {
      return new Response(
        JSON.stringify({ error: "Missing credentials" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      )
    }

    const baseUrl = zoneUrl.replace(/\/$/, "")
    const url = `${baseUrl}/atservicesrest/v1.0${endpoint}`

    const atResponse = await fetch(url, {
      method: method ?? "GET",
      headers: {
        "UserName": username,
        "Secret": secret,
        "ApiIntegrationCode": integrationCode,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    })

    const data = await atResponse.text()

    return new Response(data, {
      status: atResponse.status,
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    })
  } catch (err) {
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Unknown error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    )
  }
})
