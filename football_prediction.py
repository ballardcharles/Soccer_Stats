# Football Match Prediction Model: Poisson & Dixon-Coles
# Uses Understat data to predict match outcomes and league performance
# Author: Sports Analytics
# Date: October 2025

import pandas as pd
import numpy as np
from scipy.stats import poisson, skellam
from scipy.optimize import minimize
import warnings
warnings.filterwarnings('ignore')


class PoissonModel:
    """
    Standard Poisson regression model for football prediction.
    Assumes goals follow a Poisson distribution based on team strengths.
    """
    
    def __init__(self, xi=0.0065):
        """
        Initialize the Poisson model.
        
        Parameters:
        -----------
        xi : float
            Time decay parameter for weighting (0.0065 is original Dixon-Coles value)
        """
        self.xi = xi
        self.team_strengths = {}
        self.home_advantage = 0
        self.goals_data = None
        
    def calculate_weights(self, dates):
        """
        Apply exponential time decay to match data.
        Recent matches carry more weight than historical ones.
        
        Parameters:
        -----------
        dates : pd.Series
            Series of match dates
            
        Returns:
        --------
        np.array : Weights for each match
        """
        latest_date = dates.max()
        # Convert day differences to half-weeks (Dixon-Coles standard)
        diff_half_weeks = ((latest_date - dates).dt.days) / 3.5
        weights = np.exp(-self.xi * diff_half_weeks)
        return weights
    
    def fit(self, matches_df, home_col='HomeTeam', away_col='AwayTeam', 
            home_goals_col='HomeGoals', away_goals_col='AwayGoals', 
            date_col='Date', use_xg=False, xg_home_col=None, xg_away_col=None):
        """
        Fit the Poisson model to historical match data.
        
        Parameters:
        -----------
        matches_df : pd.DataFrame
            DataFrame containing match data
        home_col : str
            Column name for home team
        away_col : str
            Column name for away team
        home_goals_col : str
            Column name for home team goals
        away_goals_col : str
            Column name for away team goals
        date_col : str
            Column name for match dates
        use_xg : bool
            If True, use expected goals instead of actual goals
        xg_home_col : str
            Column name for home team xG (if use_xg=True)
        xg_away_col : str
            Column name for away team xG (if use_xg=True)
        """
        df = matches_df.copy()
        df[date_col] = pd.to_datetime(df[date_col])
        
        # Apply time weighting
        weights = self.calculate_weights(df[date_col])
        df['weight'] = weights
        
        # Choose goals metric
        if use_xg:
            home_goals = df[xg_home_col]
            away_goals = df[xg_away_col]
        else:
            home_goals = df[home_goals_col]
            away_goals = df[away_goals_col]
        
        # Calculate league averages (weighted)
        total_home_goals = (home_goals * weights).sum()
        total_away_goals = (away_goals * weights).sum()
        total_weight = weights.sum()
        
        self.league_home_avg = total_home_goals / total_weight
        self.league_away_avg = total_away_goals / total_weight
        
        # Calculate team attack and defense strengths
        teams = set(df[home_col].unique()) | set(df[away_col].unique())
        
        for team in teams:
            # Home performance
            home_matches = df[df[home_col] == team]
            if len(home_matches) > 0:
                home_weighted_goals = (home_matches[home_goals_col if not use_xg else xg_home_col] 
                                     * home_matches['weight']).sum()
                home_weight_sum = home_matches['weight'].sum()
                home_avg = home_weighted_goals / home_weight_sum if home_weight_sum > 0 else self.league_home_avg
            else:
                home_avg = self.league_home_avg
            
            # Away performance
            away_matches = df[df[away_col] == team]
            if len(away_matches) > 0:
                away_weighted_goals = (away_matches[away_goals_col if not use_xg else xg_away_col] 
                                     * away_matches['weight']).sum()
                away_weight_sum = away_matches['weight'].sum()
                away_avg = away_weighted_goals / away_weight_sum if away_weight_sum > 0 else self.league_away_avg
            else:
                away_avg = self.league_away_avg
            
            # Combined strength (average of home and away)
            attack_strength = (home_avg + away_avg) / 2 / max(self.league_home_avg, 0.1)
            
            self.team_strengths[team] = {
                'attack': attack_strength,
                'defense': self._calculate_defense(df, team, home_col, away_col, 
                                                   away_goals_col if not use_xg else xg_away_col),
                'home_form': home_avg,
                'away_form': away_avg
            }
        
        # Calculate home advantage
        self.home_advantage = (self.league_home_avg - self.league_away_avg)
        
        self.goals_data = df
    
    def _calculate_defense(self, df, team, home_col, away_col, goals_col):
        """Calculate team's defensive strength."""
        # Goals conceded at home
        home_def = df[df[home_col] == team][goals_col].sum()
        # Goals conceded away
        away_def = df[df[away_col] == team][goals_col].sum()
        
        total_matches = len(df[df[home_col] == team]) + len(df[df[away_col] == team])
        
        if total_matches == 0:
            return 1.0
        
        avg_conceded = (home_def + away_def) / total_matches
        defense_strength = avg_conceded / max(self.league_home_avg, 0.1)
        return defense_strength
    
    def predict_match(self, home_team, away_team, max_goals=10):
        """
        Predict match outcome probabilities using Poisson distribution.
        
        Parameters:
        -----------
        home_team : str
            Home team name
        away_team : str
            Away team name
        max_goals : int
            Maximum goals to calculate probabilities for
            
        Returns:
        --------
        dict : Contains predicted goals distributions and match outcome probabilities
        """
        # Get team strengths (default to 1.0 if team not found)
        home_attack = self.team_strengths.get(home_team, {}).get('attack', 1.0)
        home_defense = self.team_strengths.get(home_team, {}).get('defense', 1.0)
        away_attack = self.team_strengths.get(away_team, {}).get('attack', 1.0)
        away_defense = self.team_strengths.get(away_team, {}).get('defense', 1.0)
        
        # Calculate expected goals
        home_xg = self.league_home_avg * home_attack * away_defense * (1 + self.home_advantage / self.league_home_avg)
        away_xg = self.league_away_avg * away_attack * home_defense
        
        # Ensure reasonable values
        home_xg = max(0.1, min(home_xg, 15))
        away_xg = max(0.1, min(away_xg, 15))
        
        # Calculate probability distributions
        home_probs = poisson.pmf(range(max_goals), home_xg)
        away_probs = poisson.pmf(range(max_goals), away_xg)
        
        # Calculate match outcome probabilities
        home_win_prob = 0
        draw_prob = 0
        away_win_prob = 0
        
        for i in range(max_goals):
            for j in range(max_goals):
                prob = home_probs[i] * away_probs[j]
                if i > j:
                    home_win_prob += prob
                elif i == j:
                    draw_prob += prob
                else:
                    away_win_prob += prob
        
        # Normalize (in case we cut off at max_goals)
        total_prob = home_win_prob + draw_prob + away_win_prob
        home_win_prob /= total_prob
        draw_prob /= total_prob
        away_win_prob /= total_prob
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_xg': home_xg,
            'away_xg': away_xg,
            'home_win': home_win_prob,
            'draw': draw_prob,
            'away_win': away_win_prob,
            'home_probs': home_probs,
            'away_probs': away_probs
        }


class DixonColesModel(PoissonModel):
    """
    Extended Dixon-Coles model that addresses Poisson limitations.
    Adds bivariate adjustment for low-scoring matches (0-0, 1-0, 0-1, 1-1)
    and improved time decay weighting.
    """
    
    def __init__(self, xi=0.0065, tau=0.05):
        """
        Initialize the Dixon-Coles model.
        
        Parameters:
        -----------
        xi : float
            Time decay parameter for weighting
        tau : float
            Correlation parameter for bivariate adjustment
        """
        super().__init__(xi)
        self.tau = tau
        self.rho = 0  # Will be optimized
    
    def fit(self, matches_df, home_col='HomeTeam', away_col='AwayTeam',
            home_goals_col='HomeGoals', away_goals_col='AwayGoals',
            date_col='Date', optimize_rho=True, use_xg=False,
            xg_home_col=None, xg_away_col=None):
        """
        Fit Dixon-Coles model with optimization of correlation parameter.
        
        Parameters:
        -----------
        matches_df : pd.DataFrame
            DataFrame containing match data
        home_col : str
            Column name for home team
        away_col : str
            Column name for away team
        home_goals_col : str
            Column name for home goals
        away_goals_col : str
            Column name for away goals
        date_col : str
            Column name for dates
        optimize_rho : bool
            If True, optimize the correlation parameter
        use_xg : bool
            If True, use expected goals
        xg_home_col : str
            Column name for home xG
        xg_away_col : str
            Column name for away xG
        """
        # First fit the base Poisson model
        super().fit(matches_df, home_col, away_col, home_goals_col,
                   away_goals_col, date_col, use_xg, xg_home_col, xg_away_col)
        
        # Optimize rho if requested
        if optimize_rho:
            self._optimize_rho(matches_df, home_col, away_col,
                             home_goals_col, away_goals_col, date_col)
    
    def _optimize_rho(self, matches_df, home_col, away_col,
                      home_goals_col, away_goals_col, date_col):
        """
        Optimize the correlation parameter (rho) using maximum likelihood.
        """
        def negative_log_likelihood(rho):
            ll = 0
            for _, row in matches_df.iterrows():
                pred = self.predict_match(row[home_col], row[away_col])
                
                # Bivariate Poisson adjustment
                home_g = int(row[home_goals_col])
                away_g = int(row[away_goals_col])
                
                home_xg = pred['home_xg']
                away_xg = pred['away_xg']
                
                # Base Poisson probability
                prob = (poisson.pmf(home_g, home_xg) *
                       poisson.pmf(away_g, away_xg))
                
                # Apply correlation adjustment for low scores
                if (home_g + away_g) <= 2:
                    adjustment = self._dc_adjustment(home_g, away_g,
                                                    home_xg, away_xg, rho)
                    prob *= adjustment
                
                # Avoid log(0)
                if prob > 0:
                    ll += np.log(prob)
            
            return -ll
        
        # Minimize negative log-likelihood
        result = minimize(negative_log_likelihood, x0=[0.0],
                         bounds=[(-1, 1)], method='L-BFGS-B')
        
        if result.success:
            self.rho = result.x[0]
    
    def _dc_adjustment(self, home_goals, away_goals, home_xg, away_xg, rho):
        """
        Calculate the Dixon-Coles adjustment factor.
        Corrects for correlation between home and away goals in low-scoring matches.
        """
        if rho == 0:
            return 1.0
        
        # Adjustment only for specific low-score combinations
        if (home_goals == 0 and away_goals == 0):
            return 1 + rho * home_xg * away_xg
        elif (home_goals == 1 and away_goals == 1):
            return 1 - rho * home_xg * away_xg
        elif (home_goals == 0 and away_goals == 1) or (home_goals == 1 and away_goals == 0):
            return 1 - rho * home_xg * away_xg
        else:
            return 1.0
    
    def predict_match(self, home_team, away_team, max_goals=10):
        """
        Predict match with Dixon-Coles adjustments.
        
        Parameters:
        -----------
        home_team : str
            Home team name
        away_team : str
            Away team name
        max_goals : int
            Maximum goals to calculate probabilities for
            
        Returns:
        --------
        dict : Match prediction with Dixon-Coles adjustments
        """
        # Get base Poisson predictions
        pred = super().predict_match(home_team, away_team, max_goals)
        
        home_xg = pred['home_xg']
        away_xg = pred['away_xg']
        
        # Recalculate with bivariate adjustment
        home_probs = poisson.pmf(range(max_goals), home_xg)
        away_probs = poisson.pmf(range(max_goals), away_xg)
        
        home_win_prob = 0
        draw_prob = 0
        away_win_prob = 0
        
        for i in range(max_goals):
            for j in range(max_goals):
                prob = home_probs[i] * away_probs[j]
                
                # Apply Dixon-Coles adjustment
                if (i + j) <= 2:
                    adj = self._dc_adjustment(i, j, home_xg, away_xg, self.rho)
                    prob *= adj
                
                if i > j:
                    home_win_prob += prob
                elif i == j:
                    draw_prob += prob
                else:
                    away_win_prob += prob
        
        # Normalize
        total_prob = home_win_prob + draw_prob + away_win_prob
        if total_prob > 0:
            home_win_prob /= total_prob
            draw_prob /= total_prob
            away_win_prob /= total_prob
        
        pred['home_win'] = home_win_prob
        pred['draw'] = draw_prob
        pred['away_win'] = away_win_prob
        pred['rho'] = self.rho
        
        return pred


class MatchPredictor:
    """
    Unified interface for making predictions with both models.
    """
    
    def __init__(self, poisson_model=None, dixon_coles_model=None):
        """
        Initialize predictor with both models.
        
        Parameters:
        -----------
        poisson_model : PoissonModel
            Fitted Poisson model
        dixon_coles_model : DixonColesModel
            Fitted Dixon-Coles model
        """
        self.poisson = poisson_model
        self.dixon_coles = dixon_coles_model
    
    def predict_match(self, home_team, away_team, model='dixon_coles'):
        """
        Predict a match using specified model.
        
        Parameters:
        -----------
        home_team : str
            Home team name
        away_team : str
            Away team name
        model : str
            'poisson' or 'dixon_coles'
            
        Returns:
        --------
        dict : Prediction results
        """
        if model == 'dixon_coles' and self.dixon_coles:
            return self.dixon_coles.predict_match(home_team, away_team)
        elif model == 'poisson' and self.poisson:
            return self.poisson.predict_match(home_team, away_team)
        else:
            raise ValueError("Model not available or not fitted")
    
    def compare_predictions(self, home_team, away_team):
        """
        Compare Poisson and Dixon-Coles predictions side-by-side.
        
        Parameters:
        -----------
        home_team : str
            Home team name
        away_team : str
            Away team name
            
        Returns:
        --------
        pd.DataFrame : Comparison of predictions
        """
        poisson_pred = self.poisson.predict_match(home_team, away_team) if self.poisson else None
        dc_pred = self.dixon_coles.predict_match(home_team, away_team) if self.dixon_coles else None
        
        comparison_data = {
            'Metric': ['Home xG', 'Away xG', 'Home Win %', 'Draw %', 'Away Win %'],
            'Poisson': [
                f"{poisson_pred['home_xg']:.2f}",
                f"{poisson_pred['away_xg']:.2f}",
                f"{poisson_pred['home_win']*100:.1f}%",
                f"{poisson_pred['draw']*100:.1f}%",
                f"{poisson_pred['away_win']*100:.1f}%"
            ] if poisson_pred else ['N/A']*5,
            'Dixon-Coles': [
                f"{dc_pred['home_xg']:.2f}",
                f"{dc_pred['away_xg']:.2f}",
                f"{dc_pred['home_win']*100:.1f}%",
                f"{dc_pred['draw']*100:.1f}%",
                f"{dc_pred['away_win']*100:.1f}%"
            ] if dc_pred else ['N/A']*5
        }
        
        return pd.DataFrame(comparison_data)


# Example usage and testing
if __name__ == "__main__":
    # Example: Creating sample Understat-like data
    print("=" * 70)
    print("Football Prediction Model: Poisson & Dixon-Coles")
    print("=" * 70)
    
    # Create sample dataset (replace with your Understat data)
    np.random.seed(42)
    teams = ['Manchester City', 'Arsenal', 'Liverpool', 'Chelsea', 'Man United']
    dates = pd.date_range('2023-08-01', periods=100, freq='3D')
    
    matches = []
    for _ in range(100):
        home = np.random.choice(teams)
        away = np.random.choice(teams)
        if home != away:
            matches.append({
                'Date': np.random.choice(dates),
                'HomeTeam': home,
                'AwayTeam': away,
                'HomeGoals': np.random.poisson(1.5),
                'AwayGoals': np.random.poisson(1.0),
                'HomeXG': np.random.gamma(1.5, 1),
                'AwayXG': np.random.gamma(1.0, 1)
            })
    
    df = pd.DataFrame(matches)
    df = df.drop_duplicates(subset=['HomeTeam', 'AwayTeam', 'Date'])
    df = df.sort_values('Date').reset_index(drop=True)
    
    print("\nSample Data:")
    print(df.head(10))
    
    # Fit Poisson model
    print("\n" + "=" * 70)
    print("Fitting Poisson Model...")
    print("=" * 70)
    poisson_model = PoissonModel(xi=0.0065)
    poisson_model.fit(df, use_xg=True, xg_home_col='HomeXG', xg_away_col='AwayXG')
    print(f"✓ Poisson model fitted successfully")
    print(f"  League home avg (xG): {poisson_model.league_home_avg:.2f}")
    print(f"  League away avg (xG): {poisson_model.league_away_avg:.2f}")
    print(f"  Home advantage: {poisson_model.home_advantage:.2f}")
    
    # Fit Dixon-Coles model
    print("\n" + "=" * 70)
    print("Fitting Dixon-Coles Model...")
    print("=" * 70)
    dc_model = DixonColesModel(xi=0.0065, tau=0.05)
    dc_model.fit(df, optimize_rho=True, use_xg=True,
                 xg_home_col='HomeXG', xg_away_col='AwayXG')
    print(f"✓ Dixon-Coles model fitted successfully")
    print(f"  Optimized correlation parameter (rho): {dc_model.rho:.4f}")
    
    # Make predictions
    print("\n" + "=" * 70)
    print("Sample Predictions")
    print("=" * 70)
    
    predictor = MatchPredictor(poisson_model, dc_model)
    
    # Example matches
    test_matches = [
        ('Manchester City', 'Arsenal'),
        ('Liverpool', 'Chelsea'),
        ('Man United', 'Arsenal')
    ]
    
    for home, away in test_matches:
        print(f"\n{home} vs {away}")
        print("-" * 70)
        comparison = predictor.compare_predictions(home, away)
        print(comparison.to_string(index=False))
    
    # Export predictions to CSV
    print("\n" + "=" * 70)
    print("Exporting predictions...")
    print("=" * 70)
    
    all_predictions = []
    for home in teams:
        for away in teams:
            if home != away:
                dc_pred = dc_model.predict_match(home, away)
                all_predictions.append({
                    'HomeTeam': home,
                    'AwayTeam': away,
                    'HomeXG': dc_pred['home_xg'],
                    'AwayXG': dc_pred['away_xg'],
                    'HomeWinProb': dc_pred['home_win'],
                    'DrawProb': dc_pred['draw'],
                    'AwayWinProb': dc_pred['away_win'],
                    'Rho': dc_pred['rho']
                })
    
    predictions_df = pd.DataFrame(all_predictions)
    predictions_df.to_csv('match_predictions.csv', index=False)
    print("✓ Predictions exported to 'match_predictions.csv'")
    
    print("\n" + "=" * 70)
    print("Analysis complete!")
    print("=" * 70)