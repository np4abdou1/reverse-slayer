import { MetadataRoute } from 'next'

const BASE_URL = process.env.SITE_URL || 'http://51.170.140.187:8080';

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: '*', allow: '/' }],
    sitemap: [
      `${BASE_URL}/sitemap.xml`,
    ],
  };
}
