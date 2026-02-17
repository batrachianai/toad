use pyo3::prelude::*;
use std::collections::{HashMap, HashSet};

/// Get positions of first letters of words in a string
fn get_first_letters(candidate: &str) -> HashSet<usize> {
    let mut positions = HashSet::new();
    let mut in_word = false;
    
    for (i, c) in candidate.char_indices() {
        if c.is_alphanumeric() {
            if !in_word {
                positions.insert(i);
                in_word = true;
            }
        } else {
            in_word = false;
        }
    }
    
    positions
}

/// Score a search based on positions
fn score_positions(candidate: &str, positions: &[usize]) -> f64 {
    if positions.is_empty() {
        return 0.0;
    }
    
    let first_letters = get_first_letters(candidate);
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
fn match_fuzzy(query: &str, candidate: &str, case_sensitive: bool) -> Vec<(f64, Vec<usize>)> {
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
    
    let mut letter_positions: Vec<Vec<usize>> = Vec::new();
    let mut position = 0;
    
    // Find all positions for each query letter
    for (offset, letter) in query_str.chars().enumerate() {
        let candidate_chars_count = candidate_str.chars().count();
        let last_index = candidate_chars_count - offset;
        let mut positions = Vec::new();
        let mut index = position;
        
        loop {
            // Find the letter starting from index (using byte positions)
            let byte_index = candidate_str.char_indices()
                .nth(index)
                .map(|(i, _)| i)
                .unwrap_or(candidate_str.len());
            
            if let Some(byte_location) = candidate_str[byte_index..].find(letter) {
                // Convert byte offset back to character offset
                let abs_byte_location = byte_index + byte_location;
                let abs_location = candidate_str[..abs_byte_location].chars().count();
                positions.push(abs_location);
                index = abs_location + 1;
                
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
        query_str.chars().count(),
        Vec::new(),
        0,
        &mut possible_offsets,
    );
    
    // Score each combination
    possible_offsets
        .into_iter()
        .map(|offsets| {
            let score = score_positions(&candidate_str, &offsets);
            (score, offsets)
        })
        .collect()
}

/// A fuzzy search implementation in Rust
#[pyclass]
struct FuzzySearch {
    case_sensitive: bool,
    cache: HashMap<(String, String), (f64, Vec<usize>)>,
}

#[pymethods]
impl FuzzySearch {
    #[new]
    #[pyo3(signature = (case_sensitive=false))]
    fn new(case_sensitive: bool) -> Self {
        FuzzySearch {
            case_sensitive,
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
        
        let matches = match_fuzzy(query, candidate, self.case_sensitive);
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
}

/// A Python module implemented in Rust for fuzzy searching
#[pymodule]
fn _rust_fuzzy(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<FuzzySearch>()?;
    Ok(())
}
