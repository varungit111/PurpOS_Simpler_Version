import { publicEnv } from "@/config/env";

/**
 * Base URL used by shared frontend API utilities.
 *
 * Components should import higher-level API helpers later instead of calling
 * `fetch` directly, which keeps API integration logic in one place.
 */
export const API_BASE_URL = publicEnv.NEXT_PUBLIC_API_BASE_URL;
