import { Link } from 'react-router-dom';
import { CampaignStatusBadge } from './CampaignStatusBadge';

export const CampaignTable = ({ campaigns, onDelete }) => {
  return (
    <div className="campaign-table-wrap">
      <table className="campaign-table">
        <thead>
          <tr>
            <th>Campaign Name</th>
            <th>Platform</th>
            <th>Status</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {campaigns.map((campaign) => (
            <tr key={campaign.id}>
              <td>
                <div className="campaign-name-cell">
                  <strong>{campaign.name}</strong>
                  <span>{campaign.product_name}</span>
                </div>
              </td>
              <td>{campaign.platform}</td>
              <td>
                <CampaignStatusBadge status={campaign.status} />
              </td>
              <td>
                <div className="campaign-row-actions">
                  <Link to={`/campaigns/${campaign.id}`} className="table-link">View</Link>
                  <Link to={`/campaigns/${campaign.id}/edit`} className="table-link">Edit</Link>
                  <button
                    type="button"
                    className="table-link table-link-danger"
                    onClick={() => onDelete(campaign)}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default CampaignTable;
