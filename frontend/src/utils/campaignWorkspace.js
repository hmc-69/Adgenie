export const getCampaignWorkspaceFromHash = (hash) => {
  if (hash === '#creative-studio') return 'creative';
  if (hash === '#audience-analysis') return 'audience';
  if (hash === '#campaign-performance') return 'performance';
  return null;
};
