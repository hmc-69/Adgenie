import { apiClient } from './client.js';
import { getRenderedVideoPath } from '../utils/videoPlayback.js';

export const creativeService = {
  generateImageBrief: async (campaignId) => {
    console.info('[image-brief-debug]', { stage: 'generateImageBrief_service_start', campaignId });
    const response = await apiClient.post('/api/creative/image-brief', { campaign_id: Number(campaignId) });
    return response.data;
  },

  generateVideoScript: async (campaignId) => {
    const response = await apiClient.post('/api/creative/video-script', { campaign_id: Number(campaignId) });
    return response.data;
  },

  startVideoRender: async (campaignId, creativeId) => {
    const response = await apiClient.post('/api/creative/video/render', {
      campaign_id: Number(campaignId),
      creative_id: Number(creativeId),
    });
    return response.data;
  },

  getVideoRenderStatus: async (campaignId, creativeId) => {
    const response = await apiClient.get(`/api/creative/campaign/${campaignId}/video/${creativeId}/status`);
    return response.data;
  },

  getRenderedVideo: async (campaignId, creativeId, videoUrl) => {
    const response = await apiClient.get(
      getRenderedVideoPath(campaignId, creativeId, videoUrl),
      { responseType: 'blob', timeout: 120000 },
    );
    return response.data;
  },

  getImageGenerationConfig: async () => {
    const response = await apiClient.get('/api/creative/image-config');
    return response.data;
  },

  generateAdvertisementImage: async (payload) => {
    const response = await apiClient.post('/api/creative/image', payload, { timeout: 180000 });
    return response.data;
  },

  getAdvertisementImage: async (campaignId, creativeId) => {
    const response = await apiClient.get(
      `/api/creative/campaign/${campaignId}/image/${creativeId}`,
      { responseType: 'blob', timeout: 30000 },
    );
    return response.data;
  },

  listCreatives: async (campaignId) => {
    const response = await apiClient.get(`/api/creative/campaign/${campaignId}`);
    return response.data;
  },

  saveCreative: async (payload) => {
    const response = await apiClient.post('/api/creative/save', payload);
    return response.data;
  },
};

export default creativeService;
