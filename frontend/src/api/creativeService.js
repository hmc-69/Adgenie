import { apiClient } from './client';

export const creativeService = {
  generateImageBrief: async (campaignId) => {
    const response = await apiClient.post('/api/creative/image-brief', { campaign_id: Number(campaignId) });
    return response.data;
  },

  generateVideoScript: async (campaignId) => {
    const response = await apiClient.post('/api/creative/video-script', { campaign_id: Number(campaignId) });
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
