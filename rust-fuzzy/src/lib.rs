use pyo3::prelude::*;
use rayon::prelude::*;
use std::collections::{HashMap, HashSet, BinaryHeap};
use std::cmp::Ordering;

/// Scoring strategy for fuzzy search
#[derive(Debug, Clone, Copy, PartialEq)]
enum ScoringMode {
    /// Default mode: first letters are at word boundaries (\w+)
    Default,
    /// Path mode: first letters are at position 0 and after '/' characters
    Path,
}

/// A scored result for heap-based top-K tracking
#[derive(Debug, Clone)]
struct ScoredResult {
    score: f64,
    positions: Vec<usize>,
    index: usize,
}

impl PartialEq for ScoredResult {
    fn eq(&self, other: &Self) -> bool {
        self.score == other.score
    }
}

impl Eq for ScoredResult {}

impl PartialOrd for ScoredResult {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        // Reverse ordering for min-heap (we want to keep highest scores)
        other.score.partial_cmp(&self.score)
    }
}

impl Ord for ScoredResult {
    fn cmp(&self, other: &Self) -> Ordering {
        self.partial_cmp(other).unwrap_or(Ordering::Equal)
    }
}

/// Get positions of first letters of words in a string (default mode)
fn get_first_letters_default(candidate_chars: &[(usize, char)]) -> HashSet<usize> {
    let mut positions = HashSet::new();
    let mut in_word = false;
    
    for &(char_idx, c) in candidate_chars {
        if c.is_alphanumeric() {
            if !in_word {
                positions.insert(char_idx);
                in_word = true;
            }
        } else {
            in_word = false;
        }
    }
    
    positions
}

/// Get positions of first letters for path mode
/// Position 0 and positions after '/' are considered first letters
fn get_first_letters_path(candidate_chars: &[(usize, char)]) -> HashSet<usize> {
    let mut positions = HashSet::new();
    
    // Position 0 is always a first letter
    if !candidate_chars.is_empty() {
        positions.insert(0);
    }
    
    // Positions after '/' are first letters
    for window in candidate_chars.windows(2) {
        if window[0].1 == '/' {
            positions.insert(window[1].0);
        }
    }
    
    positions
}

/// Get first letters based on scoring mode
fn get_first_letters(candidate_chars: &[(usize, char)], mode: ScoringMode) -> HashSet<usize> {
    match mode {
        ScoringMode::Default => get_first_letters_default(candidate_chars),
        ScoringMode::Path => get_first_letters_path(candidate_chars),
    }
}

/// Score a search based on positions
fn score_positions(candidate_chars: &[(usize, char)], positions: &[usize], mode: ScoringMode) -> f64 {
    if positions.is_empty() {
        return 0.0;
    }
    
    let first_letters = get_first_letters(candidate_chars, mode);
    let offset_count = positions.len();
    
    // Boost first letter matches
    let first_letter_matches = positions.iter()
        .filter(|&&pos| first_letters.contains(&pos))
        .count();
    
    let mut score = (offset_count + first_letter_matches) as f64;
    
    // Count groups of consecutive matches
    let mut groups = 1;
    for i in 1..positions.len() {
        if positions[i] != positions[i - 1] + 1 {
            groups += 1;
        }
    }
    
    // Boost to favor fewer groups (more consecutive matches)
    let normalized_groups = (offset_count - (groups - 1)) as f64 / offset_count as f64;
    score *= 1.0 + (normalized_groups * normalized_groups);
    
    score
}

/// Find all possible matching offset combinations recursively
fn get_all_offsets(
    letter_positions: &[Vec<usize>],
    query_length: usize,
    current_offsets: Vec<usize>,
    positions_index: usize,
    results: &mut Vec<Vec<usize>>,
) {
    for &offset in &letter_positions[positions_index] {
        if current_offsets.is_empty() || offset > *current_offsets.last().unwrap() {
            let mut new_offsets = current_offsets.clone();
            new_offsets.push(offset);
            
            if new_offsets.len() == query_length {
                results.push(new_offsets);
            } else {
                get_all_offsets(
                    letter_positions,
                    query_length,
                    new_offsets,
                    positions_index + 1,
                    results,
                );
            }
        }
    }
}

/// Perform fuzzy matching and return all possible matches with scores
fn match_fuzzy(query: &str, candidate: &str, case_sensitive: bool, scoring_mode: ScoringMode) -> Vec<(f64, Vec<usize>)> {
    // Handle empty query
    if query.is_empty() {
        return vec![(0.0, vec![])];
    }
    
    let query_str = if case_sensitive {
        query.to_string()
    } else {
        query.to_lowercase()
    };
    
    let candidate_str = if case_sensitive {
        candidate.to_string()
    } else {
        candidate.to_lowercase()
    };
    
    // Early rejection: check if all query characters exist in candidate
    // This is much faster than full fuzzy matching for non-matches
    // Build a character frequency map for the candidate
    let mut candidate_char_set = std::collections::HashSet::with_capacity(candidate_str.len());
    for c in candidate_str.chars() {
        candidate_char_set.insert(c);
    }
    
    // Check if all query characters are present
    for query_char in query_str.chars() {
        if !candidate_char_set.contains(&query_char) {
            // Early exit - this character isn't in the candidate at all
            return vec![(0.0, vec![])];
        }
    }
    
    // Pre-compute character indices and characters for the candidate
    // This avoids repeated O(n) operations
    let candidate_chars: Vec<(usize, char)> = candidate_str
        .chars()
        .enumerate()
        .collect();
    let candidate_len = candidate_chars.len();
    
    // Build a map from character index to byte position for fast lookup
    let mut char_to_byte: Vec<usize> = Vec::with_capacity(candidate_len + 1);
    let mut byte_pos = 0;
    for (_, c) in &candidate_chars {
        char_to_byte.push(byte_pos);
        byte_pos += c.len_utf8();
    }
    char_to_byte.push(byte_pos); // Add final position
    
    let query_chars: Vec<char> = query_str.chars().collect();
    let query_len = query_chars.len();
    
    let mut letter_positions: Vec<Vec<usize>> = Vec::new();
    let mut position = 0;
    
    // Find all positions for each query letter
    for (offset, &letter) in query_chars.iter().enumerate() {
        let last_index = candidate_len - offset;
        let mut positions = Vec::new();
        let mut index = position;
        
        loop {
            if index >= candidate_len {
                break;
            }
            
            let byte_index = char_to_byte[index];
            
            if let Some(byte_offset) = candidate_str[byte_index..].find(letter) {
                // Convert byte offset back to character offset
                let abs_byte_location = byte_index + byte_offset;
                
                // Binary search or linear search to find char position
                // Since we have char_to_byte, we can find the position efficiently
                let char_pos = char_to_byte.iter()
                    .position(|&b| b == abs_byte_location)
                    .unwrap_or_else(|| {
                        // If not exact match, find the position by counting
                        candidate_str[..abs_byte_location].chars().count()
                    });
                
                positions.push(char_pos);
                index = char_pos + 1;
                
                if index >= last_index {
                    break;
                }
            } else {
                break;
            }
        }
        
        if positions.is_empty() {
            return vec![(0.0, vec![])];
        }
        
        letter_positions.push(positions);
        position = letter_positions.last().unwrap()[0] + 1;
    }
    
    // Get all possible offset combinations
    let mut possible_offsets = Vec::new();
    get_all_offsets(
        &letter_positions,
        query_len,
        Vec::new(),
        0,
        &mut possible_offsets,
    );
    
    // Score each combination
    possible_offsets
        .into_iter()
        .map(|offsets| {
            let score = score_positions(&candidate_chars, &offsets, scoring_mode);
            (score, offsets)
        })
        .collect()
}

/// A fuzzy search implementation in Rust
#[pyclass]
struct FuzzySearch {
    case_sensitive: bool,
    scoring_mode: ScoringMode,
    cache: HashMap<(String, String), (f64, Vec<usize>)>,
}

#[pymethods]
impl FuzzySearch {
    #[new]
    #[pyo3(signature = (case_sensitive=false, path_mode=false))]
    fn new(case_sensitive: bool, path_mode: bool) -> Self {
        FuzzySearch {
            case_sensitive,
            scoring_mode: if path_mode { ScoringMode::Path } else { ScoringMode::Default },
            cache: HashMap::new(),
        }
    }
    
    /// Match a query against a candidate string
    /// 
    /// Args:
    ///     query: The fuzzy query string
    ///     candidate: A candidate string to match against
    /// 
    /// Returns:
    ///     A tuple of (score, list of offsets). Returns (0.0, []) for no match.
    fn match_(&mut self, query: &str, candidate: &str) -> (f64, Vec<usize>) {
        let cache_key = (query.to_string(), candidate.to_string());
        
        if let Some(result) = self.cache.get(&cache_key) {
            return result.clone();
        }
        
        let matches = match_fuzzy(query, candidate, self.case_sensitive, self.scoring_mode);
        // Use fold to get the first max (matching Python's behavior)
        let result = matches
            .into_iter()
            .fold(None, |acc: Option<(f64, Vec<usize>)>, item| {
                match acc {
                    None => Some(item),
                    Some(current) => {
                        if item.0 > current.0 {
                            Some(item)
                        } else {
                            Some(current)
                        }
                    }
                }
            })
            .unwrap_or((0.0, vec![]));
        
        self.cache.insert(cache_key, result.clone());
        result
    }
    
    /// Clear the cache
    fn clear_cache(&mut self) {
        self.cache.clear();
    }
    
    /// Get the number of cached entries
    fn cache_size(&self) -> usize {
        self.cache.len()
    }
    
    /// Match a query against multiple candidates in parallel
    /// 
    /// Args:
    ///     query: The fuzzy query string
    ///     candidates: A list of candidate strings to match against
    /// 
    /// Returns:
    ///     A list of tuples (score, list of offsets) for each candidate.
    ///     Returns (0.0, []) for candidates with no match.
    fn match_batch(&mut self, query: &str, candidates: Vec<String>) -> Vec<(f64, Vec<usize>)> {
        // Use a threshold to decide when parallelism is worth it
        // For small batches, overhead of threading exceeds benefits
        // Benchmarks show parallel becomes beneficial around 1000 paths
        const PARALLEL_THRESHOLD: usize = 1000;
        
        if candidates.len() < PARALLEL_THRESHOLD {
            // Process serially for small batches
            candidates
                .iter()
                .map(|candidate| self.match_(query, candidate))
                .collect()
        } else {
            // For larger batches, check cache first and collect non-cached items
            let mut results = Vec::with_capacity(candidates.len());
            let mut to_process = Vec::new();
            
            for (idx, candidate) in candidates.iter().enumerate() {
                let cache_key = (query.to_string(), candidate.clone());
                if let Some(cached) = self.cache.get(&cache_key) {
                    results.push((idx, cached.clone()));
                } else {
                    to_process.push((idx, candidate.clone()));
                }
            }
            
            // Process non-cached items in parallel
            let case_sensitive = self.case_sensitive;
            let scoring_mode = self.scoring_mode;
            let query_str = query.to_string();
            
            let processed: Vec<_> = to_process
                .par_iter()
                .map(|(idx, candidate)| {
                    let matches = match_fuzzy(&query_str, candidate, case_sensitive, scoring_mode);
                    let result = matches
                        .into_iter()
                        .fold(None, |acc: Option<(f64, Vec<usize>)>, item| {
                            match acc {
                                None => Some(item),
                                Some(current) => {
                                    if item.0 > current.0 {
                                        Some(item)
                                    } else {
                                        Some(current)
                                    }
                                }
                            }
                        })
                        .unwrap_or((0.0, vec![]));
                    (*idx, candidate.clone(), result)
                })
                .collect();
            
            // Update cache and results with processed items
            for (idx, candidate, result) in processed {
                let cache_key = (query.to_string(), candidate);
                self.cache.insert(cache_key, result.clone());
                results.push((idx, result));
            }
            
            // Sort by original index and extract just the results
            results.sort_by_key(|(idx, _)| *idx);
            results.into_iter().map(|(_, result)| result).collect()
        }
    }
    
    /// Match a query against multiple candidates and return only the top K results
    /// 
    /// This is significantly faster than match_batch when you only need the best matches,
    /// as it can skip processing candidates that can't beat the current top K.
    /// 
    /// Args:
    ///     query: The fuzzy query string
    ///     candidates: A list of candidate strings to match against
    ///     k: Number of top results to return
    /// 
    /// Returns:
    ///     A list of tuples (index, score, list of offsets) for the top K matches,
    ///     sorted by score in descending order.
    fn match_batch_top_k(
        &mut self,
        query: &str,
        candidates: Vec<String>,
        k: usize,
    ) -> Vec<(usize, f64, Vec<usize>)> {
        if candidates.is_empty() || k == 0 {
            return vec![];
        }
        
        // For small batches or large K, just use regular batch matching and sort
        if candidates.len() < 1000 || k >= candidates.len() / 2 {
            let results = self.match_batch(query, candidates);
            let mut scored: Vec<_> = results
                .into_iter()
                .enumerate()
                .filter(|(_, (score, _))| *score > 0.0)
                .map(|(idx, (score, positions))| (idx, score, positions))
                .collect();
            scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));
            scored.truncate(k);
            return scored;
        }
        
        // Use a min-heap to track top K results
        let mut top_k: BinaryHeap<ScoredResult> = BinaryHeap::with_capacity(k + 1);
        let mut min_score_threshold = 0.0;
        
        let case_sensitive = self.case_sensitive;
        let scoring_mode = self.scoring_mode;
        let query_str = query.to_string();
        
        // Process in parallel with top-K tracking
        let local_results: Vec<_> = candidates
            .par_iter()
            .enumerate()
            .filter_map(|(idx, candidate)| {
                // Check cache first
                let cache_key = (query_str.clone(), candidate.clone());
                if let Some(cached) = self.cache.get(&cache_key) {
                    if cached.0 > 0.0 {
                        return Some((idx, cached.0, cached.1.clone()));
                    }
                    return None;
                }
                
                // Quick character presence check
                let candidate_lower = if case_sensitive {
                    candidate.clone()
                } else {
                    candidate.to_lowercase()
                };
                
                let query_lower = if case_sensitive {
                    query_str.clone()
                } else {
                    query_str.to_lowercase()
                };
                
                let mut char_set: HashSet<char> = HashSet::new();
                for c in candidate_lower.chars() {
                    char_set.insert(c);
                }
                
                for qc in query_lower.chars() {
                    if !char_set.contains(&qc) {
                        return None;
                    }
                }
                
                // Perform full fuzzy match
                let matches = match_fuzzy(&query_str, candidate, case_sensitive, scoring_mode);
                let result = matches
                    .into_iter()
                    .fold(None, |acc: Option<(f64, Vec<usize>)>, item| {
                        match acc {
                            None => Some(item),
                            Some(current) => {
                                if item.0 > current.0 {
                                    Some(item)
                                } else {
                                    Some(current)
                                }
                            }
                        }
                    })
                    .unwrap_or((0.0, vec![]));
                
                if result.0 > 0.0 {
                    Some((idx, result.0, result.1))
                } else {
                    None
                }
            })
            .collect();
        
        // Build top K from results
        for (idx, score, positions) in local_results {
            // Update cache first
            let cache_key = (query.to_string(), candidates[idx].clone());
            self.cache.insert(cache_key, (score, positions.clone()));
            
            if score > min_score_threshold || top_k.len() < k {
                top_k.push(ScoredResult {
                    score,
                    positions,
                    index: idx,
                });
                
                if top_k.len() > k {
                    top_k.pop();
                }
                
                if top_k.len() == k {
                    min_score_threshold = top_k.peek().map(|r| r.score).unwrap_or(0.0);
                }
            }
        }
        
        // Convert heap to sorted vec
        let mut results: Vec<_> = top_k
            .into_iter()
            .map(|r| (r.index, r.score, r.positions))
            .collect();
        
        results.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(Ordering::Equal));
        results
    }
}

/// A Python module implemented in Rust for fuzzy searching
#[pymodule]
fn _rust_fuzzy(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FuzzySearch>()?;
    Ok(())
}
