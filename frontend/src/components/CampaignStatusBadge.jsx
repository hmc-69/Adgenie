export const CampaignStatusBadge = ({ status }) => {
  const normalized = (status || 'Draft').toLowerCase();
  return (
    <span className={`campaign-status-badge status-${normalized}`}>
      {status || 'Draft'}
    </span>
  );
};

export default CampaignStatusBadge;
