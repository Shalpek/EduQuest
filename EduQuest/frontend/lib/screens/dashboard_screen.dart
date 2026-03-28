import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'lesson_screen.dart';

class DashboardScreen extends StatefulWidget {
  final int userId;
  const DashboardScreen({required this.userId, super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  Map<String, dynamic>? profile;
  List<dynamic> courses = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final p = await ApiService.getProfile(widget.userId);
    final c = await ApiService.getCourses();
    
    // Fallback data for smooth demo
    setState(() {
      profile = p ?? {'xp': 1500, 'level': 3, 'streak': 5};
      courses = c.isNotEmpty ? c : [
        {'id': 1, 'title': 'Introduction to Computer Science', 'description': 'Learn basics of programming.'}
      ];
      isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) return const Scaffold(body: Center(child: CircularProgressIndicator()));

    return Scaffold(
      appBar: AppBar(
        title: const Text('EduQuest Dashboard', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: () => Navigator.of(context).pop())
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildProfileSection(),
            const SizedBox(height: 32),
             Row(
               mainAxisAlignment: MainAxisAlignment.spaceBetween,
               children: const [
                 Text('Your Courses', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
                 Icon(Icons.library_books, color: Colors.grey)
               ],
             ),
            const SizedBox(height: 16),
            ...courses.map((c) => _buildCourseCard(c)),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileSection() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 40,
                  backgroundColor: Theme.of(context).primaryColor,
                  child: const Icon(Icons.person, size: 40, color: Colors.white),
                ),
                const SizedBox(width: 20),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Level ${profile!['level']}', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.white)),
                      const SizedBox(height: 8),
                      LinearProgressIndicator(
                         value: (profile!['xp'] % 500) / 500.0,
                         backgroundColor: Colors.white24,
                         color: Theme.of(context).colorScheme.secondary,
                         minHeight: 12,
                         borderRadius: BorderRadius.circular(6),
                      ),
                      const SizedBox(height: 8),
                      Text('${profile!['xp']} XP / ${profile!['level'] * 500} XP', style: const TextStyle(color: Colors.grey)),
                    ],
                  ),
                )
              ],
            ),
            const SizedBox(height: 20),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildStatBadge(Icons.star, '${profile!['xp']}', 'XP Earned', Colors.amber),
                _buildStatBadge(Icons.local_fire_department, '${profile!['streak']} Days', 'Streak', Colors.deepOrange),
                _buildStatBadge(Icons.emoji_events, '2', 'Badges', Colors.blueAccent),
              ],
            )
          ],
        ),
      ),
    );
  }

  Widget _buildStatBadge(IconData icon, String value, String label, Color color) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: color.withOpacity(0.2), shape: BoxShape.circle),
          child: Icon(icon, color: color, size: 28),
        ),
        const SizedBox(height: 8),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        Text(label, style: const TextStyle(color: Colors.grey, fontSize: 12)),
      ],
    );
  }

  Widget _buildCourseCard(dynamic course) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: InkWell(
        onTap: () {
          Navigator.push(context, MaterialPageRoute(
            builder: (_) => LessonScreen(courseId: course['id'], courseTitle: course['title'], userId: widget.userId)
          ));
        },
        borderRadius: BorderRadius.circular(16),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              Container(
                width: 60, height: 60,
                decoration: BoxDecoration(
                  gradient: const LinearGradient(colors: [Color(0xFF6C63FF), Color(0xFF00B4D8)]),
                  borderRadius: BorderRadius.circular(12)
                ),
                child: const Icon(Icons.code, color: Colors.white, size: 32),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(course['title'], style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 4),
                    Text(course['description'], style: const TextStyle(color: Colors.grey), maxLines: 2, overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
              const Icon(Icons.play_circle_fill, color: Color(0xFF6C63FF), size: 36),
            ],
          ),
        ),
      ),
    );
  }
}
