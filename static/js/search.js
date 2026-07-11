class TrieNode {
    constructor() {
        this.children = {};
        this.isEndOfWord = false;
        this.items = [];
        
    }
}

class Trie {
    constructor() {
        this.root = new TrieNode();
    }

    //inserts all letters from a word into Trie if they do not exist in that path already, marks end of the word and sets its url
    insert(word, url, originalName) {
        let current = this.root;
        for (let i = 0; i < word.length; i++) {
            const char = word[i].toLowerCase();
            if (!current.children[char]) {
                current.children[char] = new TrieNode();
            }
            if (char === ' ') {
                this.insert(word.substring(i+1), url, originalName)
            }
            current = current.children[char];
        }
        current.isEndOfWord = true;
        current.items.push({
            url: url,
            originalName: originalName
        });
    }

    //searches Trie for prefix user typed in. returns list of all words with this prefix using findAllWords
    searchPrefix(prefix) {
        let current = this.root;
        for (let i = 0; i < prefix.length; i++) {
            const char = prefix[i].toLowerCase();
            if (!current.children[char]) {
                return []; // Prefix not found
            }
            current = current.children[char];
        }
        
        let rawResults = []
        rawResults = this.findAllWords(current, prefix);

        const uniqueResults = new Map();
        for (const result of rawResults) {
            uniqueResults.set(result.url, result);
        }

        return Array.from(uniqueResults.values());
    }

    //recursively adds all complete words from the Trie with the users prefix, prefix parameter is used to continue recursion
    findAllWords(node, prefix) {
        let results = [];
        if (node.isEndOfWord) {
            for (const item of node.items) {
                results.push({ name: item.originalName, url: item.url });
            }
        }
        for (const char in node.children) {
            results = results.concat(this.findAllWords(node.children[char], prefix + char));
        }
        return results;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const trie = new Trie();
    trieData.forEach(item => trie.insert(item.name, item.url, item.name));

    const searchInput = document.getElementById('searchInput');
    const searchResultsContainer = document.createElement('div');
    //searchResultsContainer.className = 'list-group position-absolute mt-1 w-25';
    searchResultsContainer.className = 'list-group position-absolute mt-1 w-100'; 
    
    searchInput.closest('.search-wrapper').appendChild(searchResultsContainer);

    searchInput.addEventListener('input', () => {
        const query = searchInput.value.trim();
        searchResultsContainer.innerHTML = '';

        if (query.length > 0) {
            const suggestions = trie.searchPrefix(query);
            suggestions.slice(0, 10).forEach(suggestion => { // Limit to 10 results
                const link = document.createElement('a');
                link.href = suggestion.url;
                link.className = 'list-group-item list-group-item-action';
                link.textContent = suggestion.name;
                
                searchResultsContainer.appendChild(link);
                
            });
        }
    });

    // Hide results when clicking outside
    document.addEventListener('click', (event) => {
        if (!searchInput.contains(event.target) && !searchResultsContainer.contains(event.target)) {
            searchResultsContainer.innerHTML = '';
        }
    });

});
