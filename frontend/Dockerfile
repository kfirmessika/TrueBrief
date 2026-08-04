FROM node:22-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# Declare build-time args for NEXT_PUBLIC vars (Railway injects these automatically)
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SUPABASE_URL
ARG NEXT_PUBLIC_SUPABASE_ANON_KEY
# Optional. When set, pins the OAuth/magic-link callback origin (see
# AuthCard.callbackUrl). Leave unset and the app uses window.location.origin,
# which is correct for any single-domain deployment.
ARG NEXT_PUBLIC_SITE_URL
# Google OAuth client ID (public, safe to embed -- it's visible in every OAuth
# request anyway). Used by AuthCard's Google Identity Services sign-in. Must
# have https://<this domain> added to Authorized JavaScript origins in
# Google Cloud Console, or GIS silently fails to initialize.
ARG NEXT_PUBLIC_GOOGLE_CLIENT_ID
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_SUPABASE_URL=$NEXT_PUBLIC_SUPABASE_URL
ENV NEXT_PUBLIC_SUPABASE_ANON_KEY=$NEXT_PUBLIC_SUPABASE_ANON_KEY
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL
ENV NEXT_PUBLIC_GOOGLE_CLIENT_ID=$NEXT_PUBLIC_GOOGLE_CLIENT_ID

RUN npm run build

EXPOSE 3000
ENV PORT=3000
CMD ["npm", "start"]
