import { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { campaignService, getApiErrorMessage } from '../api/campaignService';
import { CampaignForm } from '../components/CampaignForm';
import { EMPTY_CAMPAIGN_FORM } from '../constants/campaigns';

export const CampaignNew = () => {
  const [values, setValues] = useState(EMPTY_CAMPAIGN_FORM);
  const [errorMessage, setErrorMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (event) => {
    event.preventDefault();
    setErrorMessage('');

    if (!values.name.trim() || !values.product_name.trim() || !values.description.trim() || !values.target_audience.trim()) {
      setErrorMessage('Please fill in all required campaign fields.');
      return;
    }

    if (values.budget !== '' && Number(values.budget) < 0) {
      setErrorMessage('Budget must be a valid non-negative number.');
      return;
    }

    setIsSubmitting(true);
    try {
      const created = await campaignService.createCampaign(values);
      navigate(`/campaigns/${created.id}`, {
        replace: true,
        state: { successMessage: 'Campaign created successfully.' },
      });
    } catch (error) {
      setErrorMessage(getApiErrorMessage(error, 'Unable to create campaign. Please check your input and try again.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="campaign-page">
      <div className="page-header">
        <div>
          <p className="page-kicker">Campaign Management</p>
          <h1>Create Campaign</h1>
          <p className="page-subtitle">Define the campaign details that later modules will use for AI generation and analysis.</p>
        </div>
      </div>

      {location.state?.errorMessage && (
        <div className="alert alert-error" role="alert">{location.state.errorMessage}</div>
      )}

      <div className="campaign-form-card">
        <CampaignForm
          values={values}
          onChange={setValues}
          onSubmit={handleSubmit}
          onCancel={() => navigate('/dashboard')}
          submitLabel="Create Campaign"
          isSubmitting={isSubmitting}
          errorMessage={errorMessage}
        />
      </div>
    </div>
  );
};

export default CampaignNew;
