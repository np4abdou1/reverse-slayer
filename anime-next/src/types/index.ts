export interface Anime {
  anime_id: string;
  anime_name: string;
  anime_cover_image_url: string;
  anime_rating: string | null;
  anime_type: string;
  anime_release_year: string;
  anime_status: string;
  anime_description?: string;
  anime_genres?: string;
}

export interface Episode {
  episode_id: string;
  episode_name: string;
}

export interface Server {
  id: string;
  label: string;
  name: string;
  url: string;
}
