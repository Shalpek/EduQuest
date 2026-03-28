import 'package:flutter/material.dart';
import '../services/api_service.dart';

class TeacherScreen extends StatefulWidget {
  final int userId;
  const TeacherScreen({required this.userId, super.key});

  @override
  State<TeacherScreen> createState() => _TeacherScreenState();
}

class _TeacherScreenState extends State<TeacherScreen> {
  List<dynamic> courses = [];
  List<dynamic> studentsProgress = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final c = await ApiService.getCourses();
    final s = await ApiService.getStudentsProgress();
    
    setState(() {
      courses = c;
      studentsProgress = s;
      isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    if (isLoading) return const Scaffold(body: Center(child: CircularProgressIndicator()));

    return Scaffold(
      appBar: AppBar(
        title: const Text('Teacher Dashboard', style: TextStyle(fontWeight: FontWeight.bold)),
        actions: [
          IconButton(icon: const Icon(Icons.logout), onPressed: () => Navigator.of(context).pop())
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Courses Managed', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            ...courses.map((c) => _buildCourseCard(c)),
            const SizedBox(height: 32),
            const Text('Students Progress', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 16),
            ListView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: studentsProgress.length,
              itemBuilder: (context, index) {
                final sp = studentsProgress[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor: const Color(0xFF6C63FF).withOpacity(0.2),
                      child: Text('${sp['level']}', style: const TextStyle(color: Color(0xFF6C63FF), fontWeight: FontWeight.bold)),
                    ),
                    title: Text(sp['email'], style: const TextStyle(fontWeight: FontWeight.bold)),
                    subtitle: Text('Level ${sp['level']} • XP ${sp['xp']} • Streak ${sp['streak']} Days'),
                    trailing: const Icon(Icons.show_chart, color: Colors.green),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildCourseCard(dynamic course) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        leading: Container(
          width: 48, height: 48,
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [Color(0xFF6C63FF), Color(0xFF00B4D8)]),
            borderRadius: BorderRadius.circular(12)
          ),
          child: const Icon(Icons.school, color: Colors.white),
        ),
        title: Text(course['title'], style: const TextStyle(fontWeight: FontWeight.bold)),
        subtitle: Text(course['description'], maxLines: 1, overflow: TextOverflow.ellipsis),
      ),
    );
  }
}
