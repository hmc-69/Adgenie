export const CAMPAIGN_PLATFORMS = [
  'Instagram',
  'Facebook',
  'Google Ads',
  'LinkedIn',
];

export const CAMPAIGN_OBJECTIVES = [
  'Brand Awareness',
  'Product Promotion',
  'Lead Generation',
  'Website Traffic',
  'Sales',
];

export const CAMPAIGN_TONES = [
  'Professional',
  'Casual',
  'Friendly',
  'Exciting',
  'Persuasive',
];

export const CAMPAIGN_STATUSES = ['Draft', 'Active', 'Completed'];

export const EMPTY_CAMPAIGN_FORM = {
  name: '',
  product_name: '',
  description: '',
  target_audience: '',
  platform: 'Instagram',
  objective: 'Brand Awareness',
  tone: 'Professional',
  budget: '',
  keywords: '',
  status: 'Draft',
};

export const campaignToFormValues = (campaign) => ({
  name: campaign.name || '',
  product_name: campaign.product_name || '',
  description: campaign.description || '',
  target_audience: campaign.target_audience || '',
  platform: campaign.platform || 'Instagram',
  objective: campaign.objective || 'Brand Awareness',
  tone: campaign.tone || 'Professional',
  budget: campaign.budget === null || campaign.budget === undefined ? '' : String(campaign.budget),
  keywords: campaign.keywords || '',
  status: campaign.status || 'Draft',
});
