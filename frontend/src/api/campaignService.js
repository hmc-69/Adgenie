import axios from 'axios';
import { apiClient } from './client.js';

const AUDIENCE_ANALYSIS_TIMEOUT_MS = 120_000;

export const getApiErrorMessage = (error, fallback = 'Something went wrong. Please try again.') => {
  const detail = error?.response?.data?.detail;

  if (error?.code === 'ERR_CANCELED' || error?.name === 'CanceledError' || axios.isCancel(error)) {
    return 'The request was canceled before it finished. Please try again.';
  }

  if ((error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') && /timeout/i.test(error?.message || '')) {
    return 'The request took too long to finish. Please try again.';
  }

  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => item.msg || item.message || JSON.stringify(item))
      .join(' ');
  }

  if (error?.response?.status === 401) {
    return 'Your session has expired. Please sign in again.';
  }

  if (error?.response?.status === 404) {
    return 'Campaign not found.';
  }

  if (axios.isAxiosError(error) && !error.response) {
    return 'Unable to reach the AdGenie API. Check your network connection.';
  }

  return fallback;
};

const toCampaignPayload = (formValues, { includeStatus = false } = {}) => {
  const payload = {
    name: formValues.name.trim(),
    product_name: formValues.product_name.trim(),
    description: formValues.description.trim(),
    target_audience: formValues.target_audience.trim(),
    platform: formValues.platform,
    objective: formValues.objective,
    tone: formValues.tone,
    keywords: formValues.keywords?.trim() ? formValues.keywords.trim() : null,
  };

  if (formValues.budget === '' || formValues.budget === null || formValues.budget === undefined) {
    payload.budget = null;
  } else {
    payload.budget = Number(formValues.budget);
  }

  if (includeStatus && formValues.status) {
    payload.status = formValues.status;
  }

  return payload;
};

export const campaignService = {
  createCampaign: async (formValues) => {
    const response = await apiClient.post('/api/campaigns', toCampaignPayload(formValues));
    return response.data;
  },

  getCampaigns: async () => {
    const response = await apiClient.get('/api/campaigns');
    return response.data;
  },

  getCampaign: async (campaignId) => {
    const response = await apiClient.get(`/api/campaigns/${campaignId}`);
    return response.data;
  },

  createAudienceAnalysis: async (campaignId) => {
    const response = await apiClient.post(
      `/api/campaigns/${campaignId}/audience-analysis`,
      undefined,
      { timeout: AUDIENCE_ANALYSIS_TIMEOUT_MS }
    );
    return response.data;
  },

  getAudienceAnalysisHistory: async (campaignId) => {
    const response = await apiClient.get(`/api/campaigns/${campaignId}/audience-analysis`);
    return response.data;
  },

  updateCampaign: async (campaignId, formValues) => {
    const response = await apiClient.put(
      `/api/campaigns/${campaignId}`,
      toCampaignPayload(formValues, { includeStatus: true })
    );
    return response.data;
  },

  deleteCampaign: async (campaignId) => {
    const response = await apiClient.delete(`/api/campaigns/${campaignId}`);
    return response.data;
  },
};

export default campaignService;
